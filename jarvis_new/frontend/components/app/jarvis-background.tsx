const TICKS = Array.from({ length: 48 }, (_, index) => index);
const DOTS = [
  ['12%', '22%', '2s'],
  ['19%', '71%', '5s'],
  ['28%', '18%', '1s'],
  ['70%', '16%', '4s'],
  ['83%', '29%', '0s'],
  ['91%', '67%', '3s'],
  ['73%', '79%', '6s'],
  ['38%', '85%', '2.5s'],
];

export function JarvisBackground() {
  return (
    <div
      className="jarvis-background"
      aria-hidden="true"
      style={{
        backgroundImage: 'linear-gradient(rgba(0, 0, 0, 0.28), rgba(0, 0, 0, 0.4)), url("/po_background.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
      }}
    />
  );
}
