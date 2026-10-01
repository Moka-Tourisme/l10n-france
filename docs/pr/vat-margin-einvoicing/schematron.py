"""Run the factur-x lib schematrons on generated e-invoices with SaxonC."""
import glob
import os
import sys

from lxml import etree
from saxonche import PySaxonProcessor

SCH = sys.argv[1]
XML = sys.argv[2]
SETS = {
    "facturx": ["facturx-extended/Factur-X_1.09_EXTENDED.xsl",
                "facturx-en16931/Factur-X_1.09_EN16931.xsl",
                "cii-schematron-fr-ctc/BR-FR-Flux2-Schematron-CII.xslt"],
    "cii": ["cii-extended-ctc-fr/EXTENDED-CTC-FR-CII.xslt",
            "facturx-en16931/Factur-X_1.09_EN16931.xsl",
            "cii-schematron-fr-ctc/BR-FR-Flux2-Schematron-CII.xslt"],
    "ubl": ["ubl-2.1/EN16931-UBL-validation.xslt",
            "ubl-2.1/EXTENDED-CTC-FR-UBL.xslt",
            "ubl-2.1/BR-FR-Flux2-Schematron-UBL.xslt"],
}
NS = {"svrl": "http://purl.oclc.org/dsdl/svrl"}
with PySaxonProcessor(license=False) as proc:
    xslt = proc.new_xslt30_processor()
    compiled = {}
    for path in sorted(glob.glob(os.path.join(XML, "*.xml"))):
        kind = os.path.basename(path).rsplit("-", 1)[1][:-4]
        for xsl in SETS[kind]:
            if xsl not in compiled:
                compiled[xsl] = xslt.compile_stylesheet(stylesheet_file=os.path.join(SCH, xsl))
            out = compiled[xsl].transform_to_string(source_file=path)
            svrl = etree.fromstring(out.encode())
            fired = len(svrl.xpath("//svrl:fired-rule", namespaces=NS))
            issues = svrl.xpath("//svrl:failed-assert | //svrl:successful-report", namespaces=NS)
            errors = [i for i in issues if (i.get("flag") or "fatal") in ("fatal", "error")]
            print(f"{os.path.basename(path):28} {xsl.split('/')[-1]:40} rules={fired:4} errors={len(errors)} warnings={len(issues) - len(errors)}")
            for i in issues:
                text = " ".join("".join(i.xpath("svrl:text//text()", namespaces=NS)).split())
                print(f"    [{i.get('flag')}] {i.get('id')}: {text[:220]}")
