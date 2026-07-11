import xiaobingFace from '@/assets/pet-spirit/face.png'

export function XiaobingAvatar({ className = '' }: { className?: string }) {
  return (
    <img
      src={xiaobingFace}
      alt="小冰"
      draggable={false}
      className={`select-none rounded-full object-cover object-top ${className}`}
    />
  )
}
