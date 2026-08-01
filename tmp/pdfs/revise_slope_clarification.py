from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    ContentStream,
    FloatObject,
    NameObject,
    NumberObject,
)


SOURCE = Path("/Users/mithunarun/Downloads/SPA_Manuscript___JCSM_Version (2).pdf")
OUTPUT = Path("output/pdf/SPA_Manuscript_JCSM_revised_slope_clarification.pdf")

# These eight lines replace the original five lines beginning with
# "well as SO-coupled/uncoupled." and ending immediately before citation [30].
REPLACEMENT_LINES = [
    "well as SO-coupled/uncoupled. SO phenotypes include density, amplitude, duration,",
    "and event-level rising slope (uV/s), defined from the negative peak to the next",
    "negative-to-positive zero crossing. SPA reports its mean across detected SOs. This is",
    "a local waveform-morphology measure, not overnight slow-wave activity decay across",
    "NREM cycles. Spindle-SO coupling phenotypes include overlap percentage and phase",
    "angles. For spindle detection quality control, the user can specify the quality cutoff",
    "(default 1) at the webpage that determines how much the detected spindles should",
    "stand out from the background. There is also EEG-based brain age (BA) [",
]


def justified_tj(line, widths, first_char, font_size, target_width=370.61):
    """Build a justified PDF TJ operation using the page's embedded CMR10 font."""
    words = line.split(" ")
    glyph_width = sum(
        float(widths[byte - first_char])
        for word in words
        for byte in word.encode("ascii")
    ) * font_size / 1000
    gaps = len(words) - 1
    space_width = (target_width - glyph_width) / gaps if gaps else 0
    adjustment = int(round(-space_width * 1000 / font_size))

    parts = ArrayObject()
    for index, word in enumerate(words):
        if index:
            parts.append(NumberObject(adjustment))
        parts.append(ByteStringObject(word.encode("ascii")))
    return ([parts], b"TJ")


reader = PdfReader(SOURCE)
page = reader.pages[4]
content = ContentStream(page.get_contents(), reader)

font_size = 9.9626
font = page["/Resources"]["/Font"]["/F66"].get_object()
widths = font["/Widths"].get_object()
first_char = int(font["/FirstChar"])

# The original target text is in operations 23, 25, 27, 29, and 31, each separated
# by a relative 12-point downward move. Replace those lines, then insert three more
# lines. All later body text moves down by 36 points; the footer uses an absolute
# position and remains unchanged.
for operation_index, line in zip((23, 25, 27, 29, 31), REPLACEMENT_LINES[:5]):
    content.operations[operation_index] = justified_tj(
        line, widths, first_char, font_size
    )

insert_at = 32
extra_operations = []
for line in REPLACEMENT_LINES[5:]:
    extra_operations.append(([FloatObject(0), FloatObject(-12)], b"Td"))
    extra_operations.append(justified_tj(line, widths, first_char, font_size))
content.operations[insert_at:insert_at] = extra_operations

page[NameObject("/Contents")] = content
writer = PdfWriter()
writer.append_pages_from_reader(reader)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("wb") as stream:
    writer.write(stream)

print(OUTPUT.resolve())
