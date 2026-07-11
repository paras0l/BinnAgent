import { type CSSProperties } from 'react'
import celebrateImage from '@/assets/pet-spirit/celebrate-v3.webp'
import helloImage from '@/assets/pet-spirit/hello-v2.webp'
import peekLeftImage from '@/assets/pet-spirit/peek-left.png'
import peekRightImage from '@/assets/pet-spirit/peek-right.png'
import sleepyImage from '@/assets/pet-spirit/sleepy.webp'
import stretchingImage from '@/assets/pet-spirit/stretching.webp'
import surprisedImage from '@/assets/pet-spirit/surprised.webp'
import thinkingImage from '@/assets/pet-spirit/thinking-v2.webp'
import workingImage from '@/assets/pet-spirit/working-v2.webp'
import { expressionForMotion, type PetExpression, type PetMotionState } from './petMotionMachine'

export interface PetRendererProps {
  motion: PetMotionState
  pointerX: number
  pointerY: number
  momentumX: number
  momentumY: number
  reducedMotion: boolean
  tapSequence: number
  memoryPulse: number
  peekSide?: 'left' | 'right' | null
}

const images: Record<PetExpression, string> = {
  hello: helloImage,
  thinking: thinkingImage,
  working: workingImage,
  celebrate: celebrateImage,
  surprised: surprisedImage,
  sleepy: sleepyImage,
  stretching: stretchingImage,
}

export function PetCharacterRenderer(props: PetRendererProps) {
  return <LayeredPetRenderer {...props} />
}

function LayeredPetRenderer({ motion, pointerX, pointerY, momentumX, momentumY, reducedMotion, tapSequence, memoryPulse, peekSide }: PetRendererProps) {
  const expression: PetExpression | 'peekLeft' | 'peekRight' = motion === 'peeking'
    ? (peekSide === 'left' ? 'peekRight' : 'peekLeft')
    : expressionForMotion(motion)
  const renderImages: Record<PetExpression | 'peekLeft' | 'peekRight', string> = {
    ...images,
    peekLeft: peekLeftImage,
    peekRight: peekRightImage,
  }
  return (
    <div
      className="pet-spirit__rig"
      data-motion={motion}
      data-reduced-motion={reducedMotion}
      data-tap={tapSequence % 2}
      style={{
        '--pet-look-x': pointerX,
        '--pet-look-y': pointerY,
        '--pet-momentum-x': momentumX,
        '--pet-momentum-y': momentumY,
      } as CSSProperties}
    >
      <span className="pet-spirit__aura" aria-hidden="true" />
      <span className="pet-spirit__shadow" aria-hidden="true" />
      <div className="pet-spirit__pose-stack">
        {Object.entries(renderImages).map(([name, src]) => (
          <div
            key={name}
            role={name === expression ? 'img' : undefined}
            aria-label={name === expression ? '宠物精灵小冰' : undefined}
            aria-hidden={name === expression ? undefined : true}
            data-active={name === expression}
            data-expression={name}
            className="pet-spirit__pose"
          >
            <img src={src} alt="" decoding="async" draggable={false} className="pet-spirit__layer pet-spirit__layer--body" />
            <img src={src} alt="" decoding="async" draggable={false} className="pet-spirit__layer pet-spirit__layer--head" />
            <img src={src} alt="" decoding="async" draggable={false} className="pet-spirit__layer pet-spirit__layer--wing" />
            <span className="pet-spirit__blink" aria-hidden="true" />
          </div>
        ))}
      </div>
      <span className="pet-spirit__look" aria-hidden="true" />
      {memoryPulse > 0 ? <span key={memoryPulse} className="pet-spirit__memory-crystal" aria-hidden="true" /> : null}
      <span className="pet-spirit__spark pet-spirit__spark--one" aria-hidden="true">✦</span>
      <span className="pet-spirit__spark pet-spirit__spark--two" aria-hidden="true">✧</span>
      <span className="pet-spirit__spark pet-spirit__spark--three" aria-hidden="true">·</span>
      <span className="pet-spirit__activity" aria-hidden="true">
        <i /><i /><i />
      </span>
    </div>
  )
}
