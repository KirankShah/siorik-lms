import greetingHappy from '../assets/greeting-happy.png'

interface MilestoneMascotProps {
  message: string
}

// Reuses Mr. Siorik's mascot art from player/NarrationMascot.tsx for a
// tier-completion congratulation shown in CourseCompletionModal — a
// deliberately calmer, static presentation (no idle bob/peek, no click
// affordance, no narration offer) since this is a one-off milestone beat,
// not the ongoing slide-player helper.
export function MilestoneMascot({ message }: MilestoneMascotProps) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-brand-gold/40 bg-brand-gold/10 p-3">
      <span className="relative flex h-14 w-14 shrink-0 items-center justify-center">
        <span className="absolute inset-0 rounded-full border-2 border-brand-gold bg-white shadow-sm" />
        <img src={greetingHappy} alt="" className="relative h-11 w-11 object-contain" />
      </span>
      <p className="text-sm font-medium text-neutral-800">{message}</p>
    </div>
  )
}
