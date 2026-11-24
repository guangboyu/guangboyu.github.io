---
title: LeetCode patterns
summary: Study notes on LeetCode, one pattern at a time: when it applies, the template, the problems worth drilling, and where it breaks.
---

Each note takes one pattern from my study route and works through it the same way: the one idea that makes it correct, how to tell its variants apart, a template, worked problems with animated traces, a problem table ranked by how often each one comes up, the inputs that break the pattern, and drills to answer without running code.

<!-- route -->

## Reading the animations

Each animation steps through an algorithm one decision at a time. The data sits on the left, the Python source on the right with the running line highlighted, and the caption at the bottom says why the step happened. Every frame carries its own key, and the colours mean the same thing in every animation.

Two colours give the verdict:

- <span class="swatch" style="--fill:#DBEAFE; --edge:#2563EB"></span>**Blue**: passes, is valid, is kept.
- <span class="swatch" style="--fill:#FDE3E2; --edge:#E5484D"></span>**Red**: fails, breaks the rule, or is being thrown away.

Red against blue stays readable with the common forms of colour blindness. Red against green does not, so green is never used.

The other colours stay off that axis, so none of them reads as a verdict:

- <span class="swatch" style="--fill:#E6EBF4; --edge:#7C90AE"></span>**Slate**: in the current window, or still in the live search space, not judged yet.
- <span class="swatch" style="--fill:#FEF1CD; --edge:#C98A04"></span>**Amber**: the element being examined at this step.
- <span class="swatch" style="--fill:#F1E6FE; --edge:#9333EA"></span>**Purple**: part of the best answer found so far.
- <span class="swatch" style="--fill:#CDEFF6; --edge:#0E9AA7"></span>**Cyan**: a quantity the algorithm is accumulating, such as the water in Trapping Rain Water.
- <span class="swatch" style="--fill:#F4F5F7; --edge:#E1E5EA"></span><span class="swatch" style="--fill:#FFFFFF; --edge:#D3D9E0"></span>**Grey and white**: already done with, and not reached yet.

Each animation loops and ends on a summary frame that holds for about two seconds. Click one to open it at full size.
