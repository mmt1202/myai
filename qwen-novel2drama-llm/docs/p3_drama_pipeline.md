# P3 Novel-to-Short-Drama Pipeline

P3 implements the AI short-drama specialization layer on top of the P0/P1/P2 foundation.

## Completed P3 tasks

| ID | Capability | Implemented files | Status |
| --- | --- | --- | --- |
| P3-001 | Novel parsing | `drama/novel_parser.py` | Completed |
| P3-002 | Novel-to-drama outline | `drama/outline.py` | Completed |
| P3-003 | Character system | `drama/characters.py` | Completed |
| P3-004 | Storyboard planning | `drama/storyboard.py` | Completed |
| P3-005 | AI video prompt generation | `drama/video_prompts.py` | Completed |
| P3-006 | Short-drama quality checks | `drama/quality.py` | Completed |
| P3-007 | Production workflow API / pipeline | `drama/pipeline.py`, `drama/api.py`, `drama/fastapi_router.py` | Completed |

## P3-001 Novel parsing

`drama/novel_parser.py` provides:

- chapter splitting
- character mention extraction
- worldview/genre signal extraction
- plotline and conflict hint extraction

## P3-002 Novel-to-short-drama outline

`drama/outline.py` provides:

- episode outline generation
- short-drama structure per episode
- opening hook, conflict escalation, turning point and ending cliffhanger
- series bible summary

## P3-003 Character system

`drama/characters.py` provides:

- character cards
- relationship graph
- visual profile
- voice profile
- consistency rules
- character concept prompt

## P3-004 Storyboard planning

`drama/storyboard.py` provides:

- episode-to-shot expansion
- shot order
- shot type
- camera direction
- action/dialogue/voiceover split
- estimated duration

## P3-005 AI video prompt generation

`drama/video_prompts.py` provides platform prompt adapters for:

- 即梦 / Jimeng
- 可灵 / Kling
- Runway
- Pika

Each prompt includes shot action, scene, camera, character hints, duration and aspect ratio.

## P3-006 Quality checks

`drama/quality.py` checks:

- episode/storyboard continuity
- character reference coverage
- shot action/duration completeness
- video prompt completeness

## P3-007 Production workflow API / pipeline

`drama/pipeline.py` builds the full package:

```text
novel text -> parsed novel -> outline -> character system -> storyboard -> video prompts -> quality report -> assets
```

`drama/api.py` provides pure Python API handlers:

```text
drama_parse_api
drama_outline_api
drama_characters_api
drama_storyboard_api
drama_prompts_api
drama_quality_api
drama_pipeline_api
```

`drama/fastapi_router.py` exposes the route contract under:

```text
/v1/drama/parse
/v1/drama/outline
/v1/drama/characters
/v1/drama/storyboard
/v1/drama/prompts
/v1/drama/quality
/v1/drama/pipeline
```

## CLI usage

```bash
python drama/pipeline.py \
  --input examples/novel.txt \
  --output-dir outputs/drama/demo \
  --episode-count 3 \
  --platforms jimeng,kling,runway,pika
```

## Suggested tests

```bash
python -m unittest tests.test_drama_pipeline tests.test_drama_api
```

## Boundaries

- P3 v1 is a deterministic production pipeline and prompt/workflow layer.
- It does not generate actual images, audio or video by itself.
- It does not replace human creative review.
- Platform-specific video generation calls still require provider adapters and credentials.
- Copyright/licensing checks for source novels are outside this v1 pipeline.
