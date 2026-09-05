import logging
from xml.sax.saxutils import escape as xml_escape

import anthropic
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.html import strip_tags

from courses.models import Element

from .models import SlideNarration

logger = logging.getLogger(__name__)

NARRATION_CLAUDE_MODEL = 'claude-sonnet-5'
CLAUDE_MAX_TOKENS = 2048

# One fixed, professional Azure Neural voice per language, platform-wide —
# never user- or per-slide-selectable. (locale, voice name) pairs.
AZURE_TTS_VOICES = {
    SlideNarration.Language.EN: ('en-US', 'en-US-JennyNeural'),
    SlideNarration.Language.NE: ('ne-NP', 'ne-NP-HemkalaNeural'),
}
AZURE_TTS_OUTPUT_FORMAT = 'audio-24khz-48kbitrate-mono-mp3'

# Elements other than TEXT/QUOTE carry no narratable text, but their presence
# is still worth a brief, natural mention (e.g. "as shown in the diagram")
# rather than silently vanishing from the narration.
ELEMENT_PRESENCE_NOTES = {
    Element.ElementType.IMAGE: 'An image is shown here.',
    Element.ElementType.BREAKOUT_IMAGE: 'A supporting image is shown here.',
    Element.ElementType.VIDEO_AUDIO: 'A video is shown here.',
    Element.ElementType.FILE_DOWNLOAD: 'A downloadable file is provided here.',
    Element.ElementType.EMBED: 'An embedded resource is shown here.',
    Element.ElementType.PRESENTATION_PDF: 'A presentation is shown here.',
    Element.ElementType.DIALOGUE: 'A dialogue between two characters is shown here.',
}

NARRATION_SYSTEM_PROMPT = """\
You are a professional voice-over scriptwriter for a compliance and anti-money-laundering \
(AML) training platform used by banking professionals in Nepal. Rewrite the given slide \
content into a natural, flowing spoken narration script that a narrator would read aloud.

Rules:
- Never read bullet points, headings, or lists verbatim — turn them into connected, \
spoken sentences a listener can follow without seeing the slide.
- Use plain, professional language suited to banking professionals — clear and \
conversational, but authoritative, avoiding unnecessary jargon.
- Where the content notes an image, video, diagram, or downloadable file, refer to it \
briefly and naturally (e.g. "as shown in the diagram") rather than ignoring or over-describing it.
- Output only the narration script itself — no headings, labels, speaker names, or stage directions.
- Write the entire script in {language_name}.\
"""

NEPALI_DIRECT_COMPOSITION_NOTE = (
    ' Compose the script directly and naturally in Nepali (Devanagari script) — do not '
    'write it in English first and translate; think and write in Nepali throughout.'
)


class NarrationGenerationError(Exception):
    """Raised when a slide narration script or audio file cannot be generated."""


def _build_slide_digest(slide):
    """
    Plain-text digest of a slide's narratable content, in element order:
    TEXT/QUOTE elements contribute their (HTML-stripped) text; every other
    element type contributes a short presence note instead (or nothing, for
    element types with no note defined). Returns '' if the slide has nothing
    narratable at all.
    """
    lines = []
    for element in slide.elements.all():
        if element.element_type in (Element.ElementType.TEXT, Element.ElementType.QUOTE):
            text = strip_tags(element.rich_text or '').strip()
            if text:
                prefix = 'Quote: ' if element.element_type == Element.ElementType.QUOTE else ''
                lines.append(f'{prefix}{text}')
        else:
            note = ELEMENT_PRESENCE_NOTES.get(element.element_type)
            if note:
                lines.append(f'[{note}]')
    return '\n\n'.join(lines)


def _generate_script(slide, language, digest):
    if not settings.ANTHROPIC_API_KEY:
        raise NarrationGenerationError('ANTHROPIC_API_KEY is not configured.')

    language_name = 'English' if language == SlideNarration.Language.EN else 'Nepali'
    system_prompt = NARRATION_SYSTEM_PROMPT.format(language_name=language_name)
    if language == SlideNarration.Language.NE:
        system_prompt += NEPALI_DIRECT_COMPOSITION_NOTE

    user_prompt = f'Slide title: {slide.title}\n\nSlide content:\n{digest}'

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=NARRATION_CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
    except anthropic.APIError as exc:
        logger.exception('Claude narration script generation failed for slide %s (%s)', slide.id, language)
        raise NarrationGenerationError(f'Script generation failed: {exc}') from exc

    script_text = ''.join(block.text for block in response.content if block.type == 'text').strip()
    if not script_text:
        raise NarrationGenerationError('Claude returned an empty narration script.')
    return script_text


def _fetch_azure_access_token():
    region = settings.AZURE_SPEECH_REGION
    url = f'https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    response = requests.post(
        url, headers={'Ocp-Apim-Subscription-Key': settings.AZURE_SPEECH_KEY}, timeout=15
    )
    response.raise_for_status()
    return response.text


def _synthesize_speech(script_text, language):
    if not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION:
        raise NarrationGenerationError(
            'Azure Speech credentials are not configured (AZURE_SPEECH_KEY / AZURE_SPEECH_REGION).'
        )

    locale, voice_name = AZURE_TTS_VOICES[language]
    try:
        token = _fetch_azure_access_token()
    except requests.RequestException as exc:
        logger.exception('Azure Speech token request failed')
        raise NarrationGenerationError(f'Could not authenticate with Azure Speech: {exc}') from exc

    ssml = (
        f'<speak version="1.0" xml:lang="{locale}">'
        f'<voice xml:lang="{locale}" name="{voice_name}">{xml_escape(script_text)}</voice>'
        f'</speak>'
    )
    url = f'https://{settings.AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': AZURE_TTS_OUTPUT_FORMAT,
        'User-Agent': 'lms-slide-narration',
    }
    try:
        response = requests.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception('Azure text-to-speech request failed for language %s', language)
        raise NarrationGenerationError(f'Text-to-speech request failed: {exc}') from exc

    return response.content, voice_name


def generate_slide_narration(slide, language, user):
    """
    Generate (or regenerate) the SlideNarration for `slide` in `language`:
    gather the slide's text-bearing content, have Claude rewrite it into a
    spoken narration script, send that script to Azure Neural TTS, and save
    both onto the (slide, language) SlideNarration row — creating it on first
    generation, overwriting script_text/audio_file/voice_name/generated_by on
    regeneration. Raises NarrationGenerationError for any failure along the
    way (missing credentials, no narratable content, upstream API errors).
    """
    if language not in SlideNarration.Language.values:
        raise NarrationGenerationError('Unsupported language.')

    digest = _build_slide_digest(slide)
    if not digest:
        raise NarrationGenerationError('This slide has no text content to narrate.')

    script_text = _generate_script(slide, language, digest)
    audio_bytes, voice_name = _synthesize_speech(script_text, language)

    narration, _created = SlideNarration.objects.update_or_create(
        slide=slide,
        language=language,
        defaults={
            'script_text': script_text,
            'voice_name': voice_name,
            'generated_by': user,
        },
    )
    narration.audio_file.save(f'slide-{slide.id}-{language}.mp3', ContentFile(audio_bytes), save=True)
    return narration
