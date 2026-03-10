"""
InfiniteCanvas Asset Generation Pipeline
Batch-generates 12 video segments (4 genres × 3 beats) using Veo 3.0 on Vertex AI.

Usage:
    python scripts/generate_assets.py --project your-gcp-project --bucket your-gcs-bucket
    python scripts/generate_assets.py --dry-run  # Print prompts without generating
"""

import asyncio
import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GENRES = ["noir", "romcom", "horror", "scifi"]
BEATS = ["opening", "confrontation", "climax"]
OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "video"

# ────────────────────────────────────────────────────────────────────────────
# VISUAL ANCHOR (shared across all variants for seamless transitions)
# ────────────────────────────────────────────────────────────────────────────
VISUAL_ANCHOR = """
LOCKED VISUAL ANCHORS (must match across ALL variants):
- Camera: Medium shot, slightly left-of-center framing
- Actor A: Standing at left side, facing slightly right
- Actor B: Sitting at right side of wooden table
- Table: Brown wooden table, center of frame, envelope on right corner
- Window: Background, left side, single light source direction top-right
- Duration: exactly 8 seconds
- Resolution: 720p (1280x720)
- Format: MP4 with synchronized audio
"""

# ────────────────────────────────────────────────────────────────────────────
# SCENE PROMPTS — Base narrative: "The Warehouse Confrontation"
# ────────────────────────────────────────────────────────────────────────────
PROMPTS = {
    "noir_opening": f"""
Cinematic 8-second opening scene. NOIR style: desaturated palette, deep shadows, 1940s film noir aesthetic.
A figure in a trench coat enters a dimly lit warehouse room. Jazz score begins softly.
Venetian blind shadows stripe the walls. The air is thick with cigarette smoke haze.
{VISUAL_ANCHOR}
Style: Film noir, high contrast black and white with warm amber highlights, Orson Welles lighting.
""",
    "noir_confrontation": f"""
Cinematic 8-second confrontation scene. NOIR style: desaturated palette, deep shadows.
Actor A slides a manila envelope across the wooden table toward Actor B. Tense silence.
Actor B stares at the envelope without touching it. A ceiling fan rotates slowly overhead.
Jazz score intensifies subtly. Both actors' faces partially shadowed.
{VISUAL_ANCHOR}
Style: Film noir, Venetian blind light patterns, hard shadows, moral ambiguity.
""",
    "noir_climax": f"""
Cinematic 8-second climax scene. NOIR style: high contrast shadows, fatalistic tone.
Actor B finally opens the envelope. Their expression shifts from neutral to grave realization.
Actor A watches without emotion. The truth has been revealed; consequences are inevitable.
Jazz score swells to melancholy resolution.
{VISUAL_ANCHOR}
Style: Film noir, classic Hollywood ending, shadow-heavy, cigarette smoke atmosphere.
""",
    "romcom_opening": f"""
Cinematic 8-second opening scene. ROM-COM style: warm golden hour light, vibrant colors, 2000s romantic comedy aesthetic.
A charming figure enters a sunlit café room, slightly flustered. Upbeat piano melody begins.
The room is warm, golden, inviting. Flowers on the table. Both actors look hopeful.
{VISUAL_ANCHOR}
Style: Romantic comedy, warm saturated colors, soft bokeh, Richard Curtis visual tone.
""",
    "romcom_confrontation": f"""
Cinematic 8-second confrontation scene. ROM-COM style: warm golden light, playful energy.
Actor A slides a colorful card/envelope across the wooden table, smiling nervously.
Actor B looks surprised then delighted, fingers hovering over the envelope, blushing.
Upbeat piano score. The tension is romantic, not threatening.
{VISUAL_ANCHOR}
Style: Romantic comedy, warm golden palette, soft diffused light, charming and playful.
""",
    "romcom_climax": f"""
Cinematic 8-second climax scene. ROM-COM style: bright warm light, emotional payoff.
Actor B opens the envelope revealing something meaningful (letter, photo, key).
Their face breaks into a radiant smile. Actor A watches hopefully, then relief washes over them.
Piano music swells triumphantly. This is the rom-com moment.
{VISUAL_ANCHOR}
Style: Romantic comedy, golden hour glow, warm tears of joy, Hugh Grant energy.
""",
    "horror_opening": f"""
Cinematic 8-second opening scene. HORROR style: cold desaturated blue-green palette, oppressive atmosphere.
A figure enters a shadowy room. Something feels deeply wrong. The walls seem to breathe.
Discordant ambient drone begins. Flickering fluorescent light. The table is wrong somehow.
{VISUAL_ANCHOR}
Style: Psychological horror, cold blue-green palette, James Wan visual language, uncanny valley.
""",
    "horror_confrontation": f"""
Cinematic 8-second confrontation scene. HORROR style: cold palette, visceral dread.
Actor A places a dark envelope on the table with trembling hands. It seems to pulse.
Actor B stares at it, unable to move. The ambient drone intensifies.
Something is wrong with Actor A's eyes. The envelope shouldn't exist.
{VISUAL_ANCHOR}
Style: Psychological horror, cold desaturated palette, Ari Aster visual language, dread-inducing.
""",
    "horror_climax": f"""
Cinematic 8-second climax scene. HORROR style: maximum dread, cold palette.
Actor B opens the envelope. What they see changes everything. Their face goes slack with horror.
Actor A is now smiling. The smile is wrong. The drone reaches crescendo then silence.
We understand now what this has always been.
{VISUAL_ANCHOR}
Style: Psychological horror, cold blue-grey palette, Hereditary-level dread, silence as horror.
""",
    "scifi_opening": f"""
Cinematic 8-second opening scene. SCI-FI style: cyan-blue neon lighting, holographic elements, near-future aesthetic.
A figure in near-future attire enters a sleek technological space. Synth score begins.
Holographic displays shimmer. The wooden table has a glowing interface embedded in it.
The envelope is a data chip. Everything is familiar yet transformed.
{VISUAL_ANCHOR}
Style: Sci-fi noir, Blade Runner 2049 visual language, cyan and amber neon, rain-soaked future.
""",
    "scifi_confrontation": f"""
Cinematic 8-second confrontation scene. SCI-FI style: neon-lit, technological, near-future.
Actor A places a glowing data chip on the holographic table surface. It pulses with light.
Actor B examines it without touching, their face reflected in its glow.
Synth score. The data transfer is intimate, dangerous, irreversible.
{VISUAL_ANCHOR}
Style: Sci-fi, Blade Runner neon palette, cyan-amber contrast, Denis Villeneuve pacing.
""",
    "scifi_climax": f"""
Cinematic 8-second climax scene. SCI-FI style: neon lights, technological revelation.
Actor B interfaces with the data chip. Information floods their consciousness.
Their eyes flicker with light. Actor A watches as the truth transfers.
Synth score resolves to ambient drone. The future has arrived. Nothing is the same.
{VISUAL_ANCHOR}
Style: Sci-fi, transcendent imagery, Blade Runner 2049 ending energy, cyan-amber neon.
""",
}


async def generate_video_veo3(
    prompt: str,
    output_path: Path,
    gcs_bucket: str,
    project_id: str,
    location: str = "us-central1",
    dry_run: bool = False,
) -> Optional[str]:
    """Generate a single video using Veo 3.0 on Vertex AI."""
    if dry_run:
        logger.info(f"[DRY RUN] Would generate: {output_path.name}")
        logger.info(f"Prompt preview: {prompt[:200]}...")
        return str(output_path)

    try:
        import vertexai
        from vertexai.preview.vision_models import VideoGenerationModel

        vertexai.init(project=project_id, location=location)
        model = VideoGenerationModel.from_pretrained("veo-003")

        gcs_output_uri = f"gs://{gcs_bucket}/generated/{output_path.stem}/"

        logger.info(f"Generating {output_path.name}...")
        start = time.time()

        operation = model.generate_video(
            prompt=prompt.strip(),
            output_gcs_uri=gcs_output_uri,
            duration_seconds=8,
            fps=24,
            resolution="1280x720",
        )

        # Veo generation is async — poll until complete
        result = await asyncio.get_event_loop().run_in_executor(None, operation.result)
        elapsed = time.time() - start
        logger.info(f"Generated {output_path.name} in {elapsed:.1f}s")

        # Download from GCS
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await _download_from_gcs(gcs_bucket, f"generated/{output_path.stem}/", output_path)
        return str(output_path)

    except ImportError:
        logger.error("vertexai not installed. Run: pip install google-cloud-aiplatform")
        return None
    except Exception as e:
        logger.error(f"Failed to generate {output_path.name}: {e}")
        return None


async def _download_from_gcs(bucket_name: str, prefix: str, local_path: Path):
    """Download generated video from GCS to local assets directory."""
    try:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        mp4_blobs = [b for b in blobs if b.name.endswith(".mp4")]

        if not mp4_blobs:
            logger.error(f"No MP4 found in gs://{bucket_name}/{prefix}")
            return

        mp4_blob = mp4_blobs[0]
        local_path.parent.mkdir(parents=True, exist_ok=True)
        mp4_blob.download_to_filename(str(local_path))
        logger.info(f"Downloaded {mp4_blob.name} → {local_path}")
    except Exception as e:
        logger.error(f"GCS download failed: {e}")


async def generate_all(
    project_id: str,
    gcs_bucket: str,
    location: str = "us-central1",
    dry_run: bool = False,
    concurrency: int = 3,
):
    """Generate all 12 video segments with controlled concurrency."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tasks = []
    for genre in GENRES:
        for beat in BEATS:
            key = f"{genre}_{beat}"
            prompt = PROMPTS[key]
            output_path = OUTPUT_DIR / f"{key}.mp4"

            if output_path.exists() and not dry_run:
                logger.info(f"Skipping {key}.mp4 (already exists)")
                continue

            tasks.append((key, prompt, output_path))

    if not tasks:
        logger.info("All assets already generated.")
        return

    logger.info(f"Generating {len(tasks)} video segments (concurrency={concurrency})...")

    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_generate(key, prompt, output_path):
        async with semaphore:
            return await generate_video_veo3(
                prompt, output_path, gcs_bucket, project_id, location, dry_run
            )

    results = await asyncio.gather(
        *[bounded_generate(k, p, o) for k, p, o in tasks],
        return_exceptions=True,
    )

    success = sum(1 for r in results if r and not isinstance(r, Exception))
    logger.info(f"Generation complete: {success}/{len(tasks)} segments generated")


def main():
    parser = argparse.ArgumentParser(description="InfiniteCanvas Asset Generation Pipeline")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""))
    parser.add_argument("--bucket", default=os.environ.get("GCS_BUCKET_NAME", "infinite-canvas-assets"))
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without generating")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel generation jobs")
    args = parser.parse_args()

    if not args.project and not args.dry_run:
        parser.error("--project is required (or set GOOGLE_CLOUD_PROJECT env var)")

    asyncio.run(generate_all(
        project_id=args.project,
        gcs_bucket=args.bucket,
        location=args.location,
        dry_run=args.dry_run,
        concurrency=args.concurrency,
    ))


if __name__ == "__main__":
    main()
