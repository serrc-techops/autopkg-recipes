#!/usr/bin/python

import shutil
import xml.etree.ElementTree as ET
from subprocess import Popen, PIPE
from autopkglib import Processor, ProcessorError

__all__ = ["CrisisGoVersionFixer"]


def pkgutil(*args):
    pkgutil_args = ["/usr/sbin/pkgutil"]
    pkgutil_args.extend(args)

    p = Popen(pkgutil_args, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()


class CrisisGoVersionFixer(Processor):
    description = "Determines the correct version of the MakerBot Print installer."
    input_variables = {
        "pkg_path": {
            "required": True,
            "description": "Path to pkg file to expand and read PkgInfo file to get installer version",
        },
    }
    output_variables = {
        #"additional_pkginfo": {
        #    "description": "Pkginfo dictionary containing package version.",
        #},
        "pkg_version": {
            "description": "String containing package version.",
        },
    }

    __doc__ = description

    def get_makerbotprint_pkg_version(self):
        pkgutil('--expand', self.env['pkg_path'], '/tmp/tempDir')

        tree = ET.parse('/tmp/tempDir/CrisisGo.pkg/PackageInfo')

        try:
            shutil.rmtree('/tmp/tempDir')
        except OSError as e:
            print ("Error: %s - %s." % (e.filename, e.strerror))

        if not "additional_pkginfo" in self.env:
            self.env["additional_pkginfo"] = {}

        root = tree.getroot()
        for bundle in root.iter('bundle'):
            if bundle.get('id') == 'com.crisisgomac':
                self.output("Found correct package version %s" %
                            bundle.get('CFBundleShortVersionString'))
                #self.env["additional_pkginfo"]["version"] = bundle.get('CFBundleShortVersionString')
                self.env["pkg_version"] = bundle.get('CFBundleShortVersionString')
                break

    def main(self):
        self.get_makerbotprint_pkg_version()


if __name__ == "__main__":
    processor = CrisisGoVersionFixer()
    processor.execute_shell()
