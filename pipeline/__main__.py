"""The command line of the pipeline: python3 -m pipeline <command>. See pipeline/README.md."""

import argparse
import logging
import sys
from pathlib import Path

from . import config as configuration
from . import display
from .layout import Session
from .process import edit_session, finish_session, grade_session, process_session
from .watch import Watcher


def main():
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    parser.add_argument("--config", type=Path, default=configuration.CONFIG / "pipeline.toml",
                        help="the settings (default: config/pipeline.toml)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("watch", help="process each angle as the rig shoots it, and show each complete session")
    for name, text in [
        ("session", "process every angle of a session not processed yet, then build and show its quilt"),
        ("edit", "edit the grading of a session in darktable, then grade it, build and show its quilt"),
        ("grade", "grade every merged image of a session again, then build and show its quilt"),
        ("quilt", "build and show the quilt of a session"),
    ]:
        command = commands.add_parser(name, help=text)
        command.add_argument("folder", type=Path, help="the session's folder")
        command.add_argument("--no-show", action="store_true", help="do not show the quilt on the Looking Glass")
    show = commands.add_parser("show", help="show a quilt on the Looking Glass")
    show.add_argument("quilt", type=Path)
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    config = configuration.load(arguments.config)
    try:
        if arguments.command == "watch":
            Watcher(config).run()
        elif arguments.command == "show":
            display.show(arguments.quilt, config.quilt)
        else:
            session = Session(arguments.folder)
            step = {"session": process_session, "edit": edit_session, "grade": grade_session,
                    "quilt": finish_session}[arguments.command]
            step(session, config, show=not arguments.no_show)
    except (RuntimeError, OSError) as error:
        logging.error("%s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
