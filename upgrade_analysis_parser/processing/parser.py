import re
from pathlib import Path
from typing import List, Optional

from ..models import ChangeRecord
from .db import setup_database, clear_all_changes, insert_data, db_path_for_version, ensure_db_exists

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpgradeAnalysisParser:
    RE_SECTION = re.compile(r"---(Models|Fields|XML records) in module '(.+?)'---")
    RE_MODEL = re.compile(r"^(obsolete|new) model\s+([\w\.]+)\s*(\[.+\])?$")
    RE_FIELD = re.compile(
        r"^(?P<module>\S+)\s*/\s*(?P<model>[\w\.]+)\s*/\s*(?P<field>[\w\.]+)\s*(?:\((?P<type>[\w\.]+)\))?\s*:\s*(?P<desc>.+)$"
    )
    RE_XML = re.compile(
        r"^(?P<type>NEW|DEL)\s+(?P<record_model>[\w\.]+):\s+(?P<xml_id>[\w\.]+)(?P<extra>.*)$"
    )

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        self.version = self.file_path.parent.name
        self.module = self.file_path.parent.parent.name

    def parse(self) -> List[ChangeRecord]:
        changes = []
        current_category, current_module = None, None
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                section_match = self.RE_SECTION.match(line)
                if section_match:
                    current_category = section_match.group(1).upper().replace(" ", "_")
                    current_module = section_match.group(2)
                    continue
                record = None
                if current_category == "MODELS":
                    record = self._parse_model_line(line, current_module)
                elif current_category == "FIELDS":
                    record = self._parse_field_line(line)
                elif current_category == "XML_RECORDS":
                    record = self._parse_xml_record_line(line, current_module)
                if record:
                    changes.append(record)
        return changes

    def _parse_model_line(self, line: str, module: str) -> Optional[ChangeRecord]:
        match = self.RE_MODEL.match(line)
        if not match:
            return None
        change_type, model_name, tag = match.groups()
        return ChangeRecord(
            version=self.version,
            module=module,
            change_category="MODEL",
            change_type=change_type.upper(),
            model_name=model_name,
            raw_line=line,
            details_json={"tag": tag.strip("[]") if tag else None},
        )

    def _parse_field_line(self, line: str) -> Optional[ChangeRecord]:
        match = self.RE_FIELD.match(line)
        if not match:
            return None
        data = match.groupdict()
        desc = data["desc"].strip()
        change_type = "MODIFIED"
        if desc.startswith("NEW"):
            change_type = "NEW"
        elif desc.startswith("DEL"):
            change_type = "DEL"
        return ChangeRecord(
            version=self.version,
            module=data["module"],
            change_category="FIELD",
            change_type=change_type,
            model_name=data["model"],
            field_name=data["field"],
            description=desc,
            raw_line=line,
            details_json={"field_type": data["type"]},
        )

    def _parse_xml_record_line(self, line: str, module: str) -> Optional[ChangeRecord]:
        match = self.RE_XML.match(line)
        if not match:
            return None
        data = match.groupdict()
        details = {}
        change_type = data["type"]
        if "renamed" in data["extra"]:
            change_type = "RENAMED"
            details["rename_info"] = data["extra"].strip()
        return ChangeRecord(
            version=self.version,
            module=module,
            change_category="XML_RECORD",
            change_type=change_type,
            record_model=data["record_model"],
            xml_id=data["xml_id"],
            raw_line=line,
            details_json=details,
        )


def run_parse_for_version(major_version: int, base_scripts_dir: Path):
    db_path = db_path_for_version(major_version)
    setup_database(db_path)
    clear_all_changes(db_path)

    glob_pattern = f"**/{major_version}.*/**/*upgrade_analysis.txt"
    analysis_files = list(base_scripts_dir.glob(glob_pattern))

    if not analysis_files:
        logger.warning(f"No analysis files found for version {major_version}.*")
        return

    logger.info(f"Found {len(analysis_files)} analysis files for version {major_version}.*.")
    all_changes = [change for file_path in analysis_files for change in UpgradeAnalysisParser(str(file_path)).parse()]
    
    if all_changes:
        insert_data(db_path, all_changes)