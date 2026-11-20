#!/usr/local/autopkg/python
"""Check the Authenticode signature of a downloaded .exe or .msi, and that the
expected publisher made it.

The file counts as verified only when all of this holds, for the signature and for
every signature nested in it:

 1. osslsigncode confirms the signature over what Authenticode covers: for a PE file
    (.exe) every byte except the checksum field, the certificate table's directory
    entry and the certificate table; for an MSI the content of its streams and, through
    the stream MsiDigitalSignatureEx (required here), their metadata;
 2. for a PE file, the certificate table holds exactly one entry, of the PKCS#7 kind,
    which ends at the end of the file and holds the signature and nothing but zero
    padding to 8 bytes. The signature itself still has parts that it does not cover:
    the certificates it carries can hold other bytes (a certificate that is on no
    chain is not refused), as Windows also accepts; that matters only for an installer
    that reads its own signature area. They are the only unsigned kind left: in the
    signature, in each nested one and in the timestamp, the unsigned attributes are
    limited to ALLOWED_UNSIGNED_ATTRIBUTES (the timestamp may carry none), a CRL field
    is refused, the parameters of every algorithm identifier read must be absent or
    NULL, digestAlgorithms must hold exactly the SignerInfo's digest algorithm, and the
    version numbers must be the named one-byte values. For an MSI the container is not checked: bytes after the last sector, in
    the unused part of a sector and in unused directory entries are not covered by the
    signature and are not checked here (see the README);
 3. the chain of the signing certificate ends in a root that the recipe names
    (code_signing_roots), and the chain of the timestamp in a root that the recipe
    names (timestamp_roots). Each root is a .pem file beside this processor whose DER
    has the SHA-256 written in PINNED_ROOTS; a file with another one is refused. The
    tool is given those roots and no others;
 4. the signature has a timestamp, and the tool verified it: the chain is judged at
    the time of the timestamp, so a signing certificate that has expired since, or
    that lived a few days only, still counts;
 5. the tool checked the CRL of the signing certificate and of the timestamp's
    certificate (it fetches them over HTTP from the addresses in those certificates);
    a CRL that cannot be fetched, or a certificate that names no CRL, is a refusal;
 6. the file digest and the signer's digest use an algorithm that the recipe allows
    (digest_algorithms, default SHA-256 only; MD5 is never allowed), and so does the
    timestamp's own SignerInfo;
 7. the certificate that signed (the one that the SignerInfo names by issuer and
    serial number, read here from the signature's own PKCS#7) has exactly the expected
    subject fields: every field of SIGNER_FIELDS that the recipe names is there once,
    with exactly that text, and every one that it does not name is absent. That
    certificate must be the only one in the signature with its serial number, and it
    must be the one whose chain the tool reports as verified.

The file is copied to a private temporary folder first, hashed while it is copied,
and every check runs on the copy. On success the processor sets signature_verified
(true) and signature_sha256 (the hash of the copy). The importers of this repository
count a download as verified only when signature_sha256 is the hash of the file they
import. Any doubt is a ProcessorError that names the file and the reason, and sets
nothing.

What a valid signature does not prove: that the release is harmless (a publisher's
own bad release passes), that it is the product and the version that the recipe
wants (an older or another file that the same publisher signed passes; the recipes
check the version resource or the upgrade code for that), that the publisher's key
was not stolen before the CRL said so, that a certificate revoked within the last CRL
period is caught (a CRL is fetched over HTTP and may be an older one that is still
valid), or anything about the revocation of a certificate between the signing
certificate and the root (only the signing certificate's CRL is read).
"""
import hashlib
import os
import re
import shutil
import ssl
import subprocess
import tempfile

from autopkglib import Processor, ProcessorError

__all__ = ["AuthenticodeVerifier"]

# ---- the pinned roots -----------------------------------------------------------
# name: (file beside this processor, the SHA-256 of the certificate's DER form).
# A recipe names roots by these names. Compare a fingerprint with the owner's own
# page before changing it.
PINNED_ROOTS = {
    # DigiCert Trusted Root G4 (self-signed, 2013-08-01 to 2038-01-15).
    "digicert-trusted-root-g4": (
        "digicert-trusted-root-g4.pem",
        "552f7bdcf1a7af9e6ce672017f4f12abf77240c78e761ac203d1d9d20ac89988",
    ),
    # GlobalSign Code Signing Root R45 (self-signed, 2020-03-18 to 2045-03-18).
    "globalsign-code-signing-root-r45": (
        "globalsign-code-signing-root-r45.pem",
        "7b9d553e1c92cb6e8803e137f4f287d4363757f5d44b37d52f9fca22fb97df86",
    ),
    # GlobalSign Root CA - R6 (self-signed, 2014-12-10 to 2034-12-10).
    "globalsign-root-r6": (
        "globalsign-root-r6.pem",
        "2cabeafe37d06ca22aba7391c0033d25982952c453647349763a3ab5ad6ccf69",
    ),
    # Microsoft Identity Verification Root Certificate Authority 2020 (self-signed,
    # 2020-04-16 to 2045-04-16).
    "microsoft-identity-verification-root-2020": (
        "microsoft-identity-verification-root-2020.pem",
        "5367f20c7ade0e2bca790915056d086b720c33c1fa2a2661acf787e3292e1270",
    ),
}
ROOTS_FOLDER = os.path.dirname(os.path.abspath(__file__))
MAX_PEM_CHARS = 64 * 1024

# ---- the tool ---------------------------------------------------------------
TOOL_NAME = "osslsigncode"
# Looked for in these folders only (Homebrew's two places), never on the PATH and never
# where an input says: nothing that an override or `-k` sets can name another program.
TOOL_FOLDERS = ("/opt/homebrew/bin", "/usr/local/bin")
# The version whose output this processor was written against. An older one is
# refused; a newer one that prints otherwise is refused by the checks of its output.
MIN_TOOL_VERSION = (2, 16)
# The tool fetches CRLs over the network while it verifies.
VERIFY_TIMEOUT_SECONDS = 300
OTHER_TIMEOUT_SECONDS = 60
# The environment of the tool: nothing of the run's own.
TOOL_ENV_PATH = "/usr/bin:/bin"

SIGNED_EXTENSIONS = (".exe", ".msi")
READ_BLOCK_BYTES = 1024 * 1024
MAX_SIGNATURE_BYTES = 4 * 1024 * 1024
MAX_NESTING = 8
# How many lines of the tool's output a refusal shows.
MAX_TOOL_LINES_SHOWN = 8
MAX_TOOL_LINE_CHARS = 300

# ---- the signer's name --------------------------------------------------------
# The subject fields that expected_signer may name, and their object identifiers
# (written as tuples of numbers, as decode_oid returns them).
SIGNER_FIELDS = {
    "CN": (2, 5, 4, 3),
    "O": (2, 5, 4, 10),
    "OU": (2, 5, 4, 11),
    "C": (2, 5, 4, 6),
    "L": (2, 5, 4, 7),
    "ST": (2, 5, 4, 8),
}
REQUIRED_SIGNER_FIELDS = ("CN", "O", "C")
# A field that the recipe does not name must be absent from the signer's name.
# The order in which a signer is written in the output.
SIGNER_FIELD_ORDER = ("CN", "O", "OU", "L", "ST", "C")

# ---- object identifiers of the signature --------------------------------------
OID_SIGNED_DATA = (1, 2, 840, 113549, 1, 7, 2)
OID_COUNTERSIGNATURE = (1, 2, 840, 113549, 1, 9, 6)
OID_RFC3161_TIMESTAMP = (1, 3, 6, 1, 4, 1, 311, 3, 3, 1)
OID_NESTED_SIGNATURE = (1, 3, 6, 1, 4, 1, 311, 2, 4, 1)
TIMESTAMP_OIDS = (OID_COUNTERSIGNATURE, OID_RFC3161_TIMESTAMP)
# The only unsigned attributes that a SignerInfo may carry (the signature does not cover
# them, so anything else could carry bytes of anyone's choosing). Each at most once.
ALLOWED_UNSIGNED_ATTRIBUTES = {
    OID_RFC3161_TIMESTAMP: "an RFC 3161 timestamp token (Microsoft's form)",
    OID_COUNTERSIGNATURE: "a countersignature: the older Authenticode timestamp",
    OID_NESTED_SIGNATURE: "a nested signature",
}
OID_SPC_INDIRECT_DATA = (1, 3, 6, 1, 4, 1, 311, 2, 1, 4)
# The version numbers that are accepted (RFC 5652, RFC 3161). The signature's SignedData is
# version 1 (Authenticode); a timestamp token's SignedData is version 3 (its content is a TSTInfo,
# not data); a SignerInfo that names its certificate by issuer and serial number is version 1.
# Each is written in DER as one byte: a longer integer, even with the same value, is refused.
SIGNATURE_SIGNED_DATA_VERSIONS = (1,)
TOKEN_SIGNED_DATA_VERSIONS = (3,)
SIGNER_INFO_VERSIONS = (1,)
TAG_NULL = 0x05
# The digest algorithms that a recipe may allow. MD5 is not among them: it is never accepted.
DIGEST_ALGORITHMS = {
    "sha1": (1, 3, 14, 3, 2, 26),
    "sha256": (2, 16, 840, 1, 101, 3, 4, 2, 1),
    "sha384": (2, 16, 840, 1, 101, 3, 4, 2, 2),
    "sha512": (2, 16, 840, 1, 101, 3, 4, 2, 3),
}
DIGEST_NAMES = {oid: name for name, oid in DIGEST_ALGORITHMS.items()}
DIGEST_NAMES[(1, 2, 840, 113549, 2, 5)] = "md5"
DEFAULT_DIGEST_ALGORITHMS = ("sha256",)

# ---- the containers ----------------------------------------------------------
PE_MAGIC = b"MZ"
CFB_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
PE_SIGNATURE = b"PE\0\0"
OPTIONAL_PE32 = 0x10B
OPTIONAL_PE32_PLUS = 0x20B
SECURITY_DIRECTORY = 4
WIN_CERT_REVISION_2 = 0x0200
WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002
WIN_CERT_HEADER_BYTES = 8
WIN_CERT_ALIGNMENT = 8
MAX_HEADER_BYTES = 64 * 1024
# What an MSI's output must show (osslsigncode 2.16 only warns when the stream is missing).
MSI_EXTENDED_LINES = ("Current MsiDigitalSignatureEx", "Calculated MsiDigitalSignatureEx")

# DER tags.
TAG_INTEGER = 0x02
TAG_OID = 0x06
TAG_SEQUENCE = 0x30
TAG_SET = 0x31
TAG_CONTEXT_0 = 0xA0
TAG_CONTEXT_1 = 0xA1
# The string types of a name that are read, and how.
NAME_STRING_CODECS = {
    0x0C: "utf-8",      # UTF8String
    0x13: "ascii",      # PrintableString
    0x16: "ascii",      # IA5String
    0x1E: "utf-16-be",  # BMPString
    0x1C: "utf-32-be",  # UniversalString
}

# ---- what the tool must print ------------------------------------------------
# Each signature's block of `osslsigncode verify` must hold each of these lines.
REQUIRED_BLOCK_LINES = (
    "Timestamp Server Signature CRL verification: ok",
    "Timestamp Server Signature verification: ok",
    "Signature CRL verification: ok",
    "Signature verification: ok",
)
SIGNATURE_BLOCK_PREFIX = "Signature Index:"
VERIFICATION_TIME_PREFIX = "Signature verification time:"
CODE_CHAIN_HEADER = "Signing certificate chain verified using:"
TIMESTAMP_CHAIN_HEADER = "Timestamp verified using:"
NO_TIMESTAMP_LINE = "Timestamp is not available"
COUNT_PATTERN = re.compile(r"^Number of verified signatures: (\d+)$")
FINAL_LINE = "Succeeded"
SIGNER_LINE = re.compile(r"^Signer #(\d+):$")
SERIAL_LINE = re.compile(r"^Serial : ([0-9A-Fa-f]+)$")
VERSION_LINE = re.compile(r"^osslsigncode (\d+)\.(\d+)")
# Lines worth showing when the tool refuses.
TELLING_LINE = re.compile(r"failed|error|MISMATCH|not available|revoked|expired", re.I)


class DerError(ValueError):
    """The signature is not built as expected."""


# ---- DER ---------------------------------------------------------------------


def read_element(data, pos, end):
    """(tag, content start, content end) of the element at `pos`. Only DER is read:
    one-byte tags, definite and shortest lengths, nothing past `end`."""
    if pos + 2 > end:
        raise DerError("an element is cut off")
    tag = data[pos]
    if tag & 0x1F == 0x1F:
        raise DerError("a tag of more than one byte")
    first = data[pos + 1]
    pos += 2
    if first < 0x80:
        length = first
    elif first == 0x80:
        raise DerError("an indefinite length (not DER)")
    else:
        count = first & 0x7F
        if count > 4 or pos + count > end:
            raise DerError("a length that does not fit")
        raw = data[pos:pos + count]
        length = int.from_bytes(raw, "big")
        if raw[0] == 0 or length < 0x80:
            raise DerError("a length that is not in its shortest form (not DER)")
        pos += count
    if pos + length > end:
        raise DerError("an element is longer than what holds it")
    return tag, pos, pos + length


def elements(data, start, end):
    """The elements between `start` and `end`, each (tag, element start, content
    start, content end)."""
    found = []
    pos = start
    while pos < end:
        tag, content, after = read_element(data, pos, end)
        found.append((tag, pos, content, after))
        pos = after
    return found


def expect(element, tag, what):
    if element[0] != tag:
        raise DerError("%s is not where it belongs (tag 0x%02X, expected 0x%02X)" % (what, element[0], tag))
    return element


def decode_oid(data):
    if not data or data[-1] & 0x80:
        raise DerError("an object identifier is cut off")
    numbers = []
    value = 0
    for byte in data:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            numbers.append(value)
            value = 0
    first = numbers[0]
    head = (min(first // 40, 2), first - 40 * min(first // 40, 2))
    return head + tuple(numbers[1:])


def decode_integer(data):
    if not data:
        raise DerError("an empty integer")
    return int.from_bytes(data, "big", signed=True)


def oid_of(data, element):
    expect(element, TAG_OID, "an object identifier")
    return decode_oid(data[element[2]:element[3]])


def read_name(data, element):
    """The attributes of a Name: a list of (object identifier, tag, raw value)."""
    expect(element, TAG_SEQUENCE, "a name")
    attributes = []
    for rdn in elements(data, element[2], element[3]):
        expect(rdn, TAG_SET, "a part of a name")
        for pair in elements(data, rdn[2], rdn[3]):
            expect(pair, TAG_SEQUENCE, "a field of a name")
            parts = elements(data, pair[2], pair[3])
            if len(parts) != 2:
                raise DerError("a field of a name does not have a type and a value")
            attributes.append((oid_of(data, parts[0]), parts[1][0], bytes(data[parts[1][2]:parts[1][3]])))
    return attributes


def decode_name_value(tag, raw, field):
    codec = NAME_STRING_CODECS.get(tag)
    if codec is None:
        raise DerError("the field %s of the signer's name is of a string type that is not read (0x%02X)" % (field, tag))
    try:
        return raw.decode(codec)
    except UnicodeDecodeError:
        raise DerError("the field %s of the signer's name is not valid %s" % (field, codec))


class Certificate:
    """The parts of a certificate that are compared."""

    def __init__(self, data, element):
        expect(element, TAG_SEQUENCE, "a certificate")
        parts = elements(data, element[2], element[3])
        if len(parts) != 3:
            raise DerError("a certificate does not have three parts")
        tbs = elements(data, parts[0][2], parts[0][3])
        if tbs and tbs[0][0] == TAG_CONTEXT_0:
            tbs = tbs[1:]  # the version
        if len(tbs) < 5:
            raise DerError("a certificate is too short")
        self.der = bytes(data[element[1]:element[3]])
        self.serial = decode_integer(data[expect(tbs[0], TAG_INTEGER, "a serial number")[2]:tbs[0][3]])
        self.issuer = bytes(data[tbs[2][1]:tbs[2][3]])
        self.issuer_fields = read_name(data, tbs[2])
        self.subject = read_name(data, tbs[4])


class Signature:
    """One SignerInfo of a PKCS#7 SignedData, with the certificates beside it."""

    def __init__(self, signer, timestamped, file_digest, signer_digest, timestamp_digest=None):
        self.signer = signer
        self.timestamped = timestamped
        # The digest algorithm of the timestamp's own SignerInfo.
        self.timestamp_digest = timestamp_digest
        # The algorithms (object identifiers) of the file digest that was signed and of the
        # SignerInfo's digest.
        self.file_digest = file_digest
        self.signer_digest = signer_digest


def algorithm_of(data, element, what):
    """The object identifier of an AlgorithmIdentifier. Its parameters must be absent or NULL:
    in the parts of a signature that the signature does not cover, they could carry any bytes,
    and none of the signatures seen had others (no RSASSA-PSS or ECDSA parameters)."""
    parts = elements(data, expect(element, TAG_SEQUENCE, what)[2], element[3])
    if not parts:
        raise DerError("%s is empty" % what)
    if len(parts) > 2 or (len(parts) == 2 and (parts[1][0] != TAG_NULL or parts[1][2] != parts[1][3])):
        raise DerError("%s has parameters other than NULL" % what)
    return oid_of(data, parts[0])


def check_version(data, element, allowed, what):
    """Raise DerError unless `element` is an INTEGER written as one byte with an allowed value."""
    expect(element, TAG_INTEGER, what)
    if bytes(data[element[2]:element[3]]) not in [bytes([value]) for value in allowed]:
        raise DerError("%s is not %s" % (what, " or ".join(str(value) for value in allowed)))


def check_digest_algorithms(data, fields, signer_digest, what):
    """The SignedData's digestAlgorithms must hold exactly the digest algorithm of its one SignerInfo."""
    entries = elements(data, expect(fields[1], TAG_SET, "the digestAlgorithms of " + what)[2], fields[1][3])
    found = [algorithm_of(data, entry, "a digestAlgorithms entry of " + what) for entry in entries]
    if found != [signer_digest]:
        raise DerError("the digestAlgorithms of %s hold %d entries that are not exactly the SignerInfo's digest "
                       "algorithm" % (what, len(found)))


def check_signer_info(data, info, what):
    """The version, the digest algorithm and the signature algorithm of a SignerInfo. Returns the
    digest algorithm."""
    if len(info) < 5:
        raise DerError("%s is too short" % what)
    check_version(data, info[0], SIGNER_INFO_VERSIONS, "the version of " + what)
    digest = algorithm_of(data, info[2], "the digest algorithm of " + what)
    algorithm_of(data, info[4] if info[3][0] == TAG_CONTEXT_0 else info[3], "the signature algorithm of " + what)
    return digest


def file_digest_algorithm(data, content_info):
    """The algorithm of the file digest in the SignedData's SpcIndirectDataContent."""
    parts = elements(data, expect(content_info, TAG_SEQUENCE, "the signed content")[2], content_info[3])
    if len(parts) != 2 or oid_of(data, parts[0]) != OID_SPC_INDIRECT_DATA:
        raise DerError("the signed content is not Authenticode's SpcIndirectDataContent")
    inner = elements(data, expect(parts[1], TAG_CONTEXT_0, "the SpcIndirectDataContent")[2], parts[1][3])
    if len(inner) != 1:
        raise DerError("the SpcIndirectDataContent is not one element")
    fields = elements(data, expect(inner[0], TAG_SEQUENCE, "the SpcIndirectDataContent")[2], inner[0][3])
    if len(fields) != 2:
        raise DerError("the SpcIndirectDataContent does not have two parts")
    digest = elements(data, expect(fields[1], TAG_SEQUENCE, "the file digest")[2], fields[1][3])
    if len(digest) != 2:
        raise DerError("the file digest does not have an algorithm and a value")
    return algorithm_of(data, digest[0], "the file digest's algorithm")


def dotted(oid):
    return ".".join(str(number) for number in oid)


def unsigned_attributes(data, info):
    """The unsigned attributes of a SignerInfo as a list of (object identifier, values). Only
    the kinds of ALLOWED_UNSIGNED_ATTRIBUTES, each at most once, and at most one timestamp."""
    if info[-1][0] != TAG_CONTEXT_1:
        return []
    found = []
    for attribute in elements(data, info[-1][2], info[-1][3]):
        pieces = elements(data, expect(attribute, TAG_SEQUENCE, "an unsigned attribute")[2], attribute[3])
        if len(pieces) != 2:
            raise DerError("an unsigned attribute does not have a type and values")
        kind = oid_of(data, pieces[0])
        if kind not in ALLOWED_UNSIGNED_ATTRIBUTES:
            raise DerError("a SignerInfo carries the unsigned attribute %s, which is not one of the allowed kinds "
                           "(%s): the signature does not cover it" % (dotted(kind), ", ".join(
                               dotted(oid) for oid in ALLOWED_UNSIGNED_ATTRIBUTES)))
        if any(kind == seen for seen, _ in found):
            raise DerError("a SignerInfo carries the unsigned attribute %s twice" % dotted(kind))
        values = elements(data, expect(pieces[1], TAG_SET, "the values of an attribute")[2], pieces[1][3])
        if not values or (kind in TIMESTAMP_OIDS and len(values) != 1):
            raise DerError("the unsigned attribute %s has %d values" % (dotted(kind), len(values)))
        found.append((kind, values))
    if sum(1 for kind, _ in found if kind in TIMESTAMP_OIDS) > 1:
        raise DerError("a SignerInfo carries more than one timestamp")
    return found


def signed_data_parts(data, element, what, versions=SIGNATURE_SIGNED_DATA_VERSIONS):
    """(fields of the SignedData in the ContentInfo `element`). A CRL field is refused: the
    signature does not cover it, and none of the signatures seen carried one. The version must
    be one of `versions`."""
    expect(element, TAG_SEQUENCE, what)
    parts = elements(data, element[2], element[3])
    if len(parts) != 2 or oid_of(data, parts[0]) != OID_SIGNED_DATA:
        raise DerError("%s is not a PKCS#7 SignedData" % what)
    inner = elements(data, expect(parts[1], TAG_CONTEXT_0, what)[2], parts[1][3])
    if len(inner) != 1:
        raise DerError("%s is not one element" % what)
    fields = elements(data, expect(inner[0], TAG_SEQUENCE, what)[2], inner[0][3])
    if len(fields) < 4:
        raise DerError("%s is too short" % what)
    if any(field[0] == TAG_CONTEXT_1 for field in fields[3:]):
        raise DerError("%s carries a CRL field, which the signature does not cover" % what)
    check_version(data, fields[0], versions, "the version of " + what)
    return fields


def timestamp_signer_digest(data, kind, value):
    """The digest algorithm of a timestamp's own SignerInfo, after the same rule for its unsigned
    attributes (a timestamp carries none of its own)."""
    fields = None
    if kind == OID_COUNTERSIGNATURE:
        info = elements(data, expect(value, TAG_SEQUENCE, "the countersignature")[2], value[3])
    else:
        fields = signed_data_parts(data, value, "the timestamp token", TOKEN_SIGNED_DATA_VERSIONS)
        infos = [field for field in fields[3:] if field[0] == TAG_SET]
        infos = elements(data, infos[-1][2], infos[-1][3]) if infos else []
        if len(infos) != 1:
            raise DerError("the timestamp token has %d SignerInfos, not exactly one" % len(infos))
        info = elements(data, expect(infos[0], TAG_SEQUENCE, "the timestamp's SignerInfo")[2], infos[0][3])
    digest = check_signer_info(data, info, "the timestamp's SignerInfo")
    if unsigned_attributes(data, info):
        raise DerError("the timestamp's SignerInfo carries unsigned attributes")
    if fields is not None:
        check_digest_algorithms(data, fields, digest, "the timestamp token")
    return digest


def read_signatures(data, element=None, depth=0):
    """The signature in the ContentInfo `element` (the whole of `data` when None),
    followed by every signature nested in it, in the order of the file."""
    if depth > MAX_NESTING:
        raise DerError("signatures are nested more than %d deep" % MAX_NESTING)
    if element is None:
        top = elements(data, 0, len(data))
        if len(top) != 1:
            raise DerError("the signature is not one element")
        element = top[0]
    fields = signed_data_parts(data, element, "the signature")
    file_digest = file_digest_algorithm(data, fields[2])
    certificates = []
    signer_infos = None
    for field in fields[3:]:
        if field[0] == TAG_CONTEXT_0:
            for item in elements(data, field[2], field[3]):
                if item[0] == TAG_SEQUENCE:  # other kinds of certificate are not read
                    certificates.append(Certificate(data, item))
        elif field[0] == TAG_SET:
            signer_infos = elements(data, field[2], field[3])
    if signer_infos is None:
        raise DerError("the SignedData has no SignerInfo")
    if len(signer_infos) != 1:
        raise DerError("the SignedData has %d SignerInfos, not exactly one" % len(signer_infos))
    info = elements(data, expect(signer_infos[0], TAG_SEQUENCE, "the SignerInfo")[2], signer_infos[0][3])
    if len(info) < 5:
        raise DerError("the SignerInfo is too short")
    if info[1][0] != TAG_SEQUENCE:
        raise DerError("the SignerInfo names its certificate by a key identifier, not by issuer and serial number")
    signer_digest = check_signer_info(data, info, "the SignerInfo")
    check_digest_algorithms(data, fields, signer_digest, "the signature")
    sid = elements(data, info[1][2], info[1][3])
    if len(sid) != 2:
        raise DerError("the SignerInfo's issuer and serial number are not two elements")
    issuer = bytes(data[expect(sid[0], TAG_SEQUENCE, "the SignerInfo's issuer")[1]:sid[0][3]])
    serial = decode_integer(data[expect(sid[1], TAG_INTEGER, "the SignerInfo's serial number")[2]:sid[1][3]])

    # The same certificate twice (byte for byte) is one certificate: a signing service
    # was seen to add it twice. Two different ones with the signer's serial number are
    # refused, whatever their issuer: which of them the tool took could not be told.
    same_serial = {cert.der: cert for cert in certificates if cert.serial == serial}
    if len(same_serial) != 1:
        raise DerError("the signature holds %d different certificates with the signer's serial number, not "
                       "exactly one" % len(same_serial))
    signer = list(same_serial.values())[0]
    if signer.issuer != issuer:
        raise DerError("the certificate with the signer's serial number has another issuer than the SignerInfo names")

    timestamped = False
    timestamp_digest = None
    nested = []
    for kind, values in unsigned_attributes(data, info):
        if kind in TIMESTAMP_OIDS:
            timestamped = True
            timestamp_digest = timestamp_signer_digest(data, kind, values[0])
        elif kind == OID_NESTED_SIGNATURE:
            nested.extend(values)
    signature = Signature(signer, timestamped, file_digest, signer_digest, timestamp_digest)
    found = [signature]
    for value in nested:
        found.extend(read_signatures(data, value, depth + 1))
    return found


def name_fields(attributes, field):
    """The decoded values of one field of a name."""
    oid = SIGNER_FIELDS[field]
    return [decode_name_value(tag, raw, field) for kind, tag, raw in attributes if kind == oid]


def check_signer(certificate, expected):
    """Raise DerError unless every expected field is there exactly once, with exactly
    the expected text, and every field of SIGNER_FIELDS that is not expected is absent."""
    for field in SIGNER_FIELD_ORDER:
        if field not in expected:
            count = sum(1 for kind, _, _ in certificate.subject if kind == SIGNER_FIELDS[field])
            if count:
                raise DerError("the signer's name has a field %s, which the recipe does not name (a field that "
                               "the recipe does not name must be absent)" % field)
            continue
        values = name_fields(certificate.subject, field)
        if len(values) != 1:
            raise DerError("the signer's name has %d fields %s, not exactly one" % (len(values), field))
        if values[0] != expected[field]:
            raise DerError("the signer's %s is %r, not %r" % (field, values[0][:80], expected[field]))


def check_digests(signature, allowed):
    """Raise DerError unless the file digest and the signer's digest use an allowed algorithm."""
    for what, oid in (("file digest", signature.file_digest), ("signer's digest", signature.signer_digest),
                      ("timestamp's digest", signature.timestamp_digest)):
        if oid is None:
            continue
        name = DIGEST_NAMES.get(oid, ".".join(str(number) for number in oid))
        if name not in allowed:
            raise DerError("the %s uses %s, which the recipe does not allow (digest_algorithms: %s)"
                           % (what, name, ", ".join(allowed)))


def digest_input(value):
    if value is None or value == "":
        value = list(DEFAULT_DIGEST_ALGORITHMS)
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ProcessorError("digest_algorithms must be a list of names of digest algorithms.")
    names = [item.strip().lower() for item in value if item.strip()]
    if "md5" in names:
        raise ProcessorError("digest_algorithms names md5: MD5 is never accepted.")
    unknown = sorted(set(names) - set(DIGEST_ALGORITHMS))
    if unknown or not names:
        raise ProcessorError("digest_algorithms must name some of %s; it names %s."
                             % (", ".join(sorted(DIGEST_ALGORITHMS)), ", ".join(unknown) or "none"))
    return names


def check_pe_layout(path, der):
    """Raise DerError unless the PE file's certificate table is exactly one PKCS#7 entry that
    holds `der` and nothing but zero padding to 8 bytes, and ends at the end of the file.
    The certificate table is the one part of a PE file that the signature does not cover."""
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        head = handle.read(MAX_HEADER_BYTES)
        if head[:2] != PE_MAGIC or len(head) < 0x40:
            raise DerError("the file is not a PE file (no MZ)")
        pe = int.from_bytes(head[0x3C:0x40], "little")
        if pe + 24 > len(head) or head[pe:pe + 4] != PE_SIGNATURE:
            raise DerError("the file has no PE header where its DOS header says")
        optional_size = int.from_bytes(head[pe + 20:pe + 22], "little")
        optional = pe + 24
        if optional + optional_size > len(head) or optional_size < 2:
            raise DerError("the PE optional header does not fit")
        magic = int.from_bytes(head[optional:optional + 2], "little")
        if magic == OPTIONAL_PE32:
            count_at, directories = optional + 92, optional + 96
        elif magic == OPTIONAL_PE32_PLUS:
            count_at, directories = optional + 108, optional + 112
        else:
            raise DerError("the PE optional header is neither PE32 nor PE32+")
        entry = directories + 8 * SECURITY_DIRECTORY
        if entry + 8 > optional + optional_size:
            raise DerError("the PE file has no certificate table entry")
        if int.from_bytes(head[count_at:count_at + 4], "little") <= SECURITY_DIRECTORY:
            raise DerError("the PE file has too few data directories for a certificate table")
        offset = int.from_bytes(head[entry:entry + 4], "little")
        length = int.from_bytes(head[entry + 4:entry + 8], "little")
        expected = -(-(WIN_CERT_HEADER_BYTES + len(der)) // WIN_CERT_ALIGNMENT) * WIN_CERT_ALIGNMENT
        if offset == 0 or offset % WIN_CERT_ALIGNMENT:
            raise DerError("the certificate table does not start on %d bytes (it starts at %d)"
                           % (WIN_CERT_ALIGNMENT, offset))
        if offset + length != size:
            raise DerError("the certificate table does not end at the end of the file (it starts at %d, has %d "
                           "bytes, the file has %d): bytes outside it are not covered by the signature"
                           % (offset, length, size))
        if length != expected:
            raise DerError("the certificate table has %d bytes, but one entry with this signature and its "
                           "padding has %d: it holds bytes that the signature does not cover" % (length, expected))
        handle.seek(offset)
        table = handle.read(length)
    if len(table) != length:
        raise DerError("the certificate table is cut off")
    entry_length = int.from_bytes(table[0:4], "little")
    revision = int.from_bytes(table[4:6], "little")
    kind = int.from_bytes(table[6:8], "little")
    if revision != WIN_CERT_REVISION_2 or kind != WIN_CERT_TYPE_PKCS_SIGNED_DATA:
        raise DerError("the certificate table's entry is not a PKCS#7 signature (revision 0x%04X, type 0x%04X)"
                       % (revision, kind))
    if not WIN_CERT_HEADER_BYTES + len(der) <= entry_length <= length:
        raise DerError("the certificate table's entry has a length of %d, which does not fit this signature"
                       % entry_length)
    if table[WIN_CERT_HEADER_BYTES:WIN_CERT_HEADER_BYTES + len(der)] != der:
        raise DerError("the certificate table's entry does not hold the signature that was read")
    if any(table[WIN_CERT_HEADER_BYTES + len(der):]):
        raise DerError("the certificate table holds bytes after the signature that are not zero padding: they "
                       "are not covered by the signature")


def check_container(path, extension):
    """The file's first bytes must be the kind that its extension names."""
    with open(path, "rb") as handle:
        head = handle.read(len(CFB_MAGIC))
    wanted = CFB_MAGIC if extension == ".msi" else PE_MAGIC
    if not head.startswith(wanted):
        raise DerError("the file does not begin as an %s file does" % extension)


def signer_text(expected):
    return ", ".join("%s=%s" % (field, expected[field]) for field in SIGNER_FIELD_ORDER if field in expected)


# ---- roots, inputs and the tool ------------------------------------------------


def certificate_serial(der):
    data = memoryview(der)
    top = elements(data, 0, len(data))
    if len(top) != 1:
        raise DerError("not one element")
    return Certificate(data, top[0]).serial


def load_root(name, roots=None, folder=None):
    """(DER, serial number) of a pinned root, after checking that its file holds
    exactly one certificate with the pinned SHA-256."""
    table = PINNED_ROOTS if roots is None else roots
    if name not in table:
        raise ProcessorError("%r is not a pinned root. The pinned roots are: %s."
                             % (name, ", ".join(sorted(table))))
    filename, pinned = table[name]
    path = os.path.join(folder or ROOTS_FOLDER, filename)
    try:
        with open(path, "r", encoding="ascii") as handle:
            text = handle.read(MAX_PEM_CHARS + 1)
    except (OSError, UnicodeDecodeError) as err:
        raise ProcessorError("The pinned root %s cannot be read: %s" % (filename, err))
    if len(text) > MAX_PEM_CHARS:
        raise ProcessorError("The pinned root %s is larger than %d characters." % (filename, MAX_PEM_CHARS))
    blocks = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", text, re.S)
    if len(blocks) != 1:
        raise ProcessorError("The pinned root %s holds %d certificates, not exactly one." % (filename, len(blocks)))
    try:
        der = ssl.PEM_cert_to_DER_cert(blocks[0])
    except ValueError as err:
        raise ProcessorError("The pinned root %s is not a certificate: %s" % (filename, err))
    if hashlib.sha256(der).hexdigest() != pinned:
        raise ProcessorError("The pinned root %s does not have the SHA-256 written for %s in the processor; it is "
                             "not used." % (filename, name))
    try:
        serial = certificate_serial(der)
    except DerError as err:
        raise ProcessorError("The pinned root %s cannot be read: %s." % (filename, err))
    return der, serial


def root_names(value, what):
    """A list of root names from a list or from one text with commas."""
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ProcessorError("%s must be a list of names of pinned roots." % what)
    names = [item.strip() for item in value if item.strip()]
    if not names:
        raise ProcessorError("%s names no root. The pinned roots are: %s." % (what, ", ".join(sorted(PINNED_ROOTS))))
    return names


def expected_signer_input(value):
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProcessorError("expected_signer must be a dictionary of subject fields (CN, O, C, ...).")
    unknown = sorted(set(value) - set(SIGNER_FIELDS))
    if unknown:
        raise ProcessorError("expected_signer names fields that are not compared: %s. The fields are: %s."
                             % (", ".join(unknown), ", ".join(SIGNER_FIELD_ORDER)))
    missing = [field for field in REQUIRED_SIGNER_FIELDS if field not in value]
    if missing:
        raise ProcessorError("expected_signer must give %s; it lacks %s."
                             % (", ".join(REQUIRED_SIGNER_FIELDS), ", ".join(missing)))
    for field, text in value.items():
        if not isinstance(text, str) or not text.strip() or text != text.strip():
            raise ProcessorError("expected_signer's %s must be a text without white space around it." % field)
    return dict(value)


def find_tool():
    for folder in TOOL_FOLDERS:
        candidate = os.path.join(folder, TOOL_NAME)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise ProcessorError(
        "%s was not found in %s. Install it (brew install osslsigncode). Without it no signature is checked."
        % (TOOL_NAME, " or ".join(TOOL_FOLDERS)))


def run_tool(tool, arguments, timeout):
    environment = {"PATH": TOOL_ENV_PATH, "HOME": os.environ.get("HOME", "/")}
    try:
        result = subprocess.run(
            [tool] + arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, env=environment,
        )
    except subprocess.TimeoutExpired:
        raise ProcessorError("%s did not end within %d seconds." % (TOOL_NAME, timeout))
    except OSError as err:
        raise ProcessorError("%s could not be started: %s" % (TOOL_NAME, err))
    return (result.returncode, result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"))


def tool_version(tool):
    code, out, err = run_tool(tool, ["--version"], OTHER_TIMEOUT_SECONDS)
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    match = VERSION_LINE.match(lines[0]) if lines else None
    if code != 0 or not match:
        raise ProcessorError("%s --version did not say its version (exit code %d)." % (tool, code))
    number = (int(match.group(1)), int(match.group(2)))
    if number < MIN_TOOL_VERSION:
        raise ProcessorError("%s is version %d.%d; this processor needs %d.%d or later (its output was read with "
                             "that version)." % ((tool,) + number + MIN_TOOL_VERSION))
    return lines[0].rstrip(":").rstrip(",").replace(", using", "") + (" (%s)" % lines[1] if len(lines) > 1 else "")


def telling_lines(*texts):
    shown = []
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            if line and TELLING_LINE.search(line) and line not in shown:
                shown.append(line[:MAX_TOOL_LINE_CHARS])
    return shown[:MAX_TOOL_LINES_SHOWN]


def chain_serials(lines, header):
    """The serial numbers of the chain that follows `header` in a block, by signer
    number (0 is the signing certificate)."""
    try:
        start = lines.index(header)
    except ValueError:
        return None
    serials = {}
    current = None
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.startswith("-"):
            break
        text = line.strip()
        signer = SIGNER_LINE.match(text)
        if signer:
            current = int(signer.group(1))
            continue
        serial = SERIAL_LINE.match(text)
        if serial and current is not None and current not in serials:
            serials[current] = int(serial.group(1), 16)
    if not serials or sorted(serials) != list(range(len(serials))):
        return None
    return [serials[index] for index in range(len(serials))]


def read_verify_output(out, count, msi=False):
    """Check the output of `osslsigncode verify` (standard output only). Returns, for
    each signature block, (signing time text, code chain serials, timestamp chain
    serials). For an MSI the output must show the MsiDigitalSignatureEx digest, as read
    and as calculated, and the two must be the same. Raises DerError with the reason."""
    lines = out.splitlines()
    stripped = [line.strip() for line in lines]
    if msi:
        values = []
        for prefix in MSI_EXTENDED_LINES:
            found = [line.split(":", 1)[1].split()[0] for line in stripped
                     if line.startswith(prefix) and ":" in line and line.split(":", 1)[1].split()]
            if len(found) != 1:
                raise DerError("the MSI has no MsiDigitalSignatureEx (the tool printed %d line(s) %r); without it "
                               "the metadata of the streams is not covered" % (len(found), prefix))
            values.append(found[0])
        if values[0] != values[1]:
            raise DerError("the MSI's MsiDigitalSignatureEx does not match")
    final = [line for line in stripped if line]
    if not final or final[-1] != FINAL_LINE:
        raise DerError("the tool's last line is not %r" % FINAL_LINE)
    counted = [COUNT_PATTERN.match(line) for line in stripped]
    counted = [int(match.group(1)) for match in counted if match]
    if counted != [count]:
        raise DerError("the tool did not report %d verified signature(s)" % count)
    starts = [index for index, line in enumerate(stripped) if line.startswith(SIGNATURE_BLOCK_PREFIX)]
    if len(starts) != count:
        raise DerError("the tool printed %d signature(s), the file holds %d" % (len(starts), count))
    blocks = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(lines)
        block = lines[start:end]
        block_text = [line.strip() for line in block]
        index_text = block_text[0][len(SIGNATURE_BLOCK_PREFIX):].split()
        if not index_text or index_text[0] != str(number):
            raise DerError("the tool's signatures are not in the order of the file")
        if NO_TIMESTAMP_LINE in block_text:
            raise DerError("signature %d has no timestamp" % number)
        for needed in REQUIRED_BLOCK_LINES:
            if needed not in block_text:
                raise DerError("signature %d: the tool did not print %r" % (number, needed))
        times = [line[len(VERIFICATION_TIME_PREFIX):].strip() for line in block_text
                 if line.startswith(VERIFICATION_TIME_PREFIX)]
        if len(times) != 1 or not times[0]:
            raise DerError("signature %d: the tool did not say at which time it judged the chain" % number)
        code_chain = chain_serials(block, CODE_CHAIN_HEADER)
        stamp_chain = chain_serials(block, TIMESTAMP_CHAIN_HEADER)
        if not code_chain or not stamp_chain:
            raise DerError("signature %d: the tool did not print both chains it verified" % number)
        blocks.append((times[0], code_chain, stamp_chain))
    return blocks


def copy_and_hash(source, target):
    digest = hashlib.sha256()
    with open(source, "rb") as reader, open(target, "xb") as writer:
        for block in iter(lambda: reader.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
            writer.write(block)
    return digest.hexdigest()


class AuthenticodeVerifier(Processor):
    description = __doc__
    input_variables = {
        "pathname": {
            "required": True,
            "description": "The downloaded .exe or .msi.",
        },
        "expected_signer": {
            "required": True,
            "description": (
                "The subject fields of the certificate that must have signed: a dictionary with CN, O and C, "
                "and every one of OU, L and ST that the certificate carries. Each is compared exactly, as text; "
                "a field of these six that the dictionary does not name must be absent from the certificate."
            ),
        },
        "code_signing_roots": {
            "required": True,
            "description": "The pinned roots (by name) that the signing certificate's chain may end in.",
        },
        "timestamp_roots": {
            "required": True,
            "description": "The pinned roots (by name) that the timestamp's chain may end in.",
        },
        "digest_algorithms": {
            "required": False,
            "default": list(DEFAULT_DIGEST_ALGORITHMS),
            "description": (
                "The digest algorithms that the file digest and the signer may use: a list, or one text with "
                "commas, of %s. Default: sha256 only. MD5 is never accepted." % ", ".join(sorted(DIGEST_ALGORITHMS))
            ),
        },
    }
    output_variables = {
        "signature_verified": {"description": "True: the signature, the signer and the timestamp were verified."},
        "signature_sha256": {"description": "The SHA-256 of the file that was checked (lower-case hex)."},
        "authenticode_signer": {"description": "The fields of the signer that were compared."},
        "authenticode_signing_time": {"description": "The time of the timestamp, at which the chain was judged."},
        "authenticode_tool": {"description": "The osslsigncode and OpenSSL versions that checked the file."},
    }

    def main(self):
        path = self.env.get("pathname")
        if not isinstance(path, str) or not os.path.isfile(path):
            raise ProcessorError("pathname is not a file: %r" % (path,))
        name = os.path.basename(path)
        extension = os.path.splitext(name)[1].lower()
        if extension not in SIGNED_EXTENSIONS:
            raise ProcessorError("%s: only %s files are checked." % (name, " and ".join(SIGNED_EXTENSIONS)))
        try:
            expected = expected_signer_input(self.env.get("expected_signer"))
            code_names = root_names(self.env.get("code_signing_roots"), "code_signing_roots")
            stamp_names = root_names(self.env.get("timestamp_roots"), "timestamp_roots")
            code_roots = [load_root(root) for root in code_names]
            stamp_roots = [load_root(root) for root in stamp_names]
            allowed = digest_input(self.env.get("digest_algorithms"))
            tool = find_tool()
            version = tool_version(tool)
        except ProcessorError as err:
            raise ProcessorError("%s was not checked: %s" % (name, err))

        work = tempfile.mkdtemp(prefix="authenticode-")
        try:
            copy = os.path.join(work, "file" + extension)
            try:
                sha256 = copy_and_hash(path, copy)
            except OSError as err:
                raise ProcessorError("Could not read %s: %s" % (name, err))
            try:
                check_container(copy, extension)
            except DerError as err:
                raise ProcessorError("%s: %s." % (name, err))
            code_file = os.path.join(work, "code-roots.pem")
            stamp_file = os.path.join(work, "timestamp-roots.pem")
            for target, roots in ((code_file, code_roots), (stamp_file, stamp_roots)):
                with open(target, "x", encoding="ascii") as handle:
                    handle.write("".join(ssl.DER_cert_to_PEM_cert(der) for der, _ in roots))

            signature_file = os.path.join(work, "signature.p7")
            code, out, err = run_tool(tool, ["extract-signature", "-in", copy, "-out", signature_file],
                                      OTHER_TIMEOUT_SECONDS)
            if code != 0 or not os.path.isfile(signature_file):
                raise ProcessorError("%s has no Authenticode signature that %s can read (exit code %d): %s"
                                     % (name, TOOL_NAME, code, "; ".join(telling_lines(out, err)) or "no reason given"))
            if os.path.getsize(signature_file) > MAX_SIGNATURE_BYTES:
                raise ProcessorError("%s: the signature is larger than %d bytes." % (name, MAX_SIGNATURE_BYTES))
            with open(signature_file, "rb") as handle:
                data = memoryview(handle.read())
            try:
                signatures = read_signatures(data)
            except DerError as err:
                raise ProcessorError("%s: the signature cannot be read: %s." % (name, err))
            if extension == ".exe":
                try:
                    check_pe_layout(copy, bytes(data))
                except DerError as err:
                    raise ProcessorError("%s: %s." % (name, err))
            for number, signature in enumerate(signatures):
                if not signature.timestamped:
                    raise ProcessorError("%s: signature %d has no timestamp. Without one the chain would be judged "
                                         "today, and an expired signing certificate would fail or a revoked one "
                                         "pass unseen; a signature without a timestamp is refused." % (name, number))
                try:
                    check_digests(signature, allowed)
                except DerError as err:
                    raise ProcessorError("%s: signature %d: %s." % (name, number, err))
                try:
                    check_signer(signature.signer, expected)
                except DerError as err:
                    raise ProcessorError("%s is not signed by the expected publisher (%s): signature %d: %s."
                                         % (name, signer_text(expected), number, err))

            code, out, err = run_tool(tool, ["verify", "-in", copy, "-CAfile", code_file, "-TSA-CAfile", stamp_file],
                                      VERIFY_TIMEOUT_SECONDS)
            if code != 0:
                raise ProcessorError("%s: %s refused the signature (exit code %d): %s"
                                     % (name, TOOL_NAME, code, "; ".join(telling_lines(out, err)) or "no reason given"))
            try:
                blocks = read_verify_output(out, len(signatures), msi=extension == ".msi")
            except DerError as err:
                raise ProcessorError("%s: the output of %s verify does not show a complete check: %s."
                                     % (name, TOOL_NAME, err))
            code_serials = {serial for _, serial in code_roots}
            stamp_serials = {serial for _, serial in stamp_roots}
            for number, (signature, (_, code_chain, stamp_chain)) in enumerate(zip(signatures, blocks)):
                if code_chain[0] != signature.signer.serial:
                    raise ProcessorError("%s: signature %d: the certificate whose chain %s verified is not the one "
                                         "that the signature names as its signer." % (name, number, TOOL_NAME))
                if code_chain[-1] not in code_serials:
                    raise ProcessorError("%s: signature %d: the signing chain does not end in one of %s."
                                         % (name, number, ", ".join(code_names)))
                if stamp_chain[-1] not in stamp_serials:
                    raise ProcessorError("%s: signature %d: the timestamp's chain does not end in one of %s."
                                         % (name, number, ", ".join(stamp_names)))
        finally:
            shutil.rmtree(work, ignore_errors=True)

        self.env["signature_verified"] = True
        self.env["signature_sha256"] = sha256
        self.env["authenticode_signer"] = signer_text(expected)
        self.env["authenticode_signing_time"] = blocks[0][0]
        self.env["authenticode_tool"] = version
        self.output("Signature verified: %s, signed by %s, timestamp %s%s; SHA-256 %s"
                    % (name, signer_text(expected), blocks[0][0],
                       " (%d signatures)" % len(signatures) if len(signatures) > 1 else "", sha256))
        self.output("Checked with %s" % version, verbose_level=2)


if __name__ == "__main__":
    PROCESSOR = AuthenticodeVerifier()
    PROCESSOR.execute_shell()
