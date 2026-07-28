from django.db import models

from accounts.validators import validate_image_size
from courses.models import Enrollment, Slide

# Keeps the authoring UI a manageable flat list (no graph canvas) rather than
# trying to support arbitrarily large decision trees.
MAX_NODES_PER_SLIDE = 10


class ScenarioNode(models.Model):
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='scenario_nodes')
    node_key = models.SlugField(max_length=50)
    prompt = models.TextField(blank=True, default='')
    prompt_image = models.ImageField(upload_to='scenario_node_images/', blank=True, null=True, validators=[validate_image_size])
    # Exactly one node per slide should have this set — the player's entry
    # point into the decision tree. Enforced in ScenarioNodeViewSet, not the
    # DB, same as elsewhere in this codebase (e.g. Choice.is_correct).
    is_start = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']
        unique_together = ('slide', 'node_key')

    def __str__(self):
        return f'{self.slide.display_title()} - {self.node_key}'


class ScenarioChoice(models.Model):
    node = models.ForeignKey(ScenarioNode, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=500)
    # Null means picking this choice ends the scenario.
    next_node = models.ForeignKey(
        ScenarioNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_choices'
    )
    feedback_text = models.TextField(blank=True, default='')
    is_recommended = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.choice_text


class ScenarioAttempt(models.Model):
    """
    A completed run through a scenario — created once, when the learner
    reaches an ending choice (next_node is null). SlideProgress is what
    actually gates the learner's ability to move on (see courses app); this
    is purely a reporting log of which path they took to get there.
    """

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='scenario_attempts')
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='scenario_attempts')
    # Ordered list of ScenarioChoice ids, in the order they were picked.
    path_taken = models.JSONField(default=list, blank=True)
    reached_recommended_ending = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f'{self.enrollment} - {self.slide}'
