#!/usr/bin/python

from autopkglib import Processor, ProcessorError

__all__ = ["KiteStudentPortalURLFixer"]

class KiteStudentPortalURLFixer(Processor):
    description = "Replaces spaces in Kite Student Portal download URL."
    input_variables = {
        "url": {
            "required": True,
            "description": "Download URL containing spaces.",
        },
    }
    output_variables = {
        "url": {
            "description": "Download URL with spaces replaced by '%20'.",
        },
    }

    __doc__ = description

    def main(self):
        self.env["url"] = self.env["url"][:len(self.env["url"])].replace(' ', '%20')

if __name__ == "__main__":
    processor = KiteStudentPortalURLFixer()
    processor.execute_shell()
