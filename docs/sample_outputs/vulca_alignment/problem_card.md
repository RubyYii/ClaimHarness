# Problem Card

## Project

VLM Cultural Interpretation Alignment for Chinese Painting

## Alignment Profile

`chinese_painting`

## Source Problem

# Chinese Painting Commentary Alignment

I want to evaluate whether VLMs understand Chinese painting commentary rather than only recognizing image objects. The domain problem involves visible image details, brushwork, blank space, inscriptions, commentary, historical context, and culturally situated interpretation.

The risk is that the AI task becomes generic captioning. Object recognition and caption similarity are not enough because visual elements may carry cultural or aesthetic meaning only when aligned with commentary and context.

## Domain Goal

Evaluate whether VLM outputs align visible image details, commentary text, historical context, and culturally situated interpretation.

## Not Allowed Goal

object-only captioning as cultural understanding

## Meaningful Outputs

- Region-commentary alignment evidence
- Cultural concept fidelity notes
- Uncertainty-aware interpretation candidates

## Non-Meaningful Outputs

- Generic object captioning
- Universal symbolic claims without textual or historical support
