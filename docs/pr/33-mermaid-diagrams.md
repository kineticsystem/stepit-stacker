# Diagrams as SVG Images, from Mermaid Sources

Pull request [#33](https://github.com/kineticsystem/stepit-stacker/pull/33), branch `mermaid-diagrams`.

## Goal

The two diagrams of `docs/ARCHITECTURE.md` in the style of the `beautiful-mermaid-diagrams` skill: colours by role, compact, readable in light and dark mode. StepIt Macro made the same change in [stepit-macro#103](https://github.com/kineticsystem/stepit-macro/pull/103).

## Decisions

**An SVG image, not a Mermaid block.** GitHub stretches a Mermaid block to the width of the page, so a narrow diagram becomes very tall. An image shows at the width we give it. The source stays beside it, in `docs/diagrams/<name>.mmd`.

**A hash, not a render, in the tests.** `bin/render-diagrams.sh` writes the SHA-256 of the source into the first line of the SVG. `bin/check-diagrams.sh` compares the two, so it needs neither Node.js nor Chrome. Whoever changes a `.mmd` renders it and commits both.

**The check runs with the tests.** The repository has no CI, so `./bin/pipeline.sh test` runs `bin/check-diagrams.sh` after the unit tests.

**The watcher outside the zone of the steps.** In the big picture, the arrows from rosbridge and the web server crossed the title of the computer's zone. The watcher sits above the zone now, named `THE STEPS`, and the arrows reach it clear of any title.

## Left Out

The submodules, `modules/raw-converter` and `modules/stepit-grader`: they get the same change in their own pull requests. Their pointers move in a later update, once those are merged.

The big picture is about 1,100 px tall, over the skill's 900: it is narrow, 719 px, and splitting it would lose the one view of the rig and this computer together.
