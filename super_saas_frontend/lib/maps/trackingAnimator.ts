import type { LngLatTuple } from "./types";

export interface AnimatableMarker {
  setPosition(position: LngLatTuple): void;
}

export class TrackingAnimator {
  private animationFrameId: number | null = null;

  constructor(private readonly marker: AnimatableMarker, private readonly durationMs = 700) {}

  animate(from: LngLatTuple, to: LngLatTuple): void {
    this.cancel();

    const [fromLng, fromLat] = from;
    const [toLng, toLat] = to;
    const startedAt = performance.now();

    const step = (now: number) => {
      const progress = Math.min((now - startedAt) / this.durationMs, 1);
      const lng = fromLng + (toLng - fromLng) * progress;
      const lat = fromLat + (toLat - fromLat) * progress;

      this.marker.setPosition([lng, lat]);

      if (progress < 1) {
        this.animationFrameId = window.requestAnimationFrame(step);
      } else {
        this.animationFrameId = null;
      }
    };

    this.animationFrameId = window.requestAnimationFrame(step);
  }

  cancel(): void {
    if (this.animationFrameId !== null) {
      window.cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }
}
