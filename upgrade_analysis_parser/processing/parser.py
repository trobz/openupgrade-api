# Copyright 2025 Trobz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import re, ast
from pathlib import Path
from typing import List, Optional

from ..models import ChangeRecord
from .db import setup_database, clear_all_changes, insert_data, db_path_for_version, ensure_db_exists

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpgradeAnalysisParser:
    RE_SECTION = re.compile(r"---(Models|Fields|XML records) in module '(.+?)'---")
    RE_MODEL = re.compile(
        r"^(obsolete|new) model\s+([\w\.]+)\s*(?:\((?P<paren>.+?)\))?\s*(?:\[(?P<tag>.+?)\])?$"
    )
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
        change_type = match.group(1)
        model_name = match.group(2)
        paren = match.group("paren")
        tag = match.group("tag")
        details = {}
        if paren and ("renamed from" in paren or "renamed to" in paren):
            details["rename_info"] = paren.strip()
        if tag:
            details["tag"] = tag
        return ChangeRecord(
            version=self.version,
            module=module,
            change_category="MODEL",
            change_type=change_type.upper(),
            model_name=model_name,
            raw_line=line,
            details_json=details,
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

def parse_pre_migration_for_renamed_fields(py_path: Path) -> list[tuple[str, str, str]]:
    """Parse a pre-migration.py file to collect rename_fields tuples.

    Returns list of (model, old_field, new_field, '').
    """
    try:
        source = py_path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Map variable name -> list of (model, old_field, new_field)
    tuple_assignments: dict[str, list[tuple[str, str, str]]] = {}

    def _extract_tuple_list_from_sequence(node: ast.AST) -> list[tuple[str, str, str]] | None:
        """Extract tuples from a List/Tuple literal.

        Supports both 3-tuple: (model, old, new) and 4-tuple: (model, table, old, new)
        by always taking element[0] as model and the last two elements as old/new.
        """
        items: list[tuple[str, str, str]] = []
        seq = node.elts if isinstance(node, (ast.List, ast.Tuple)) else None
        if seq is None:
            return None
        for elt in seq:
            if isinstance(elt, (ast.List, ast.Tuple)) and len(elt.elts) >= 3:
                # Use first element as model, and the last two as old/new
                model_node = elt.elts[0]
                old_node = elt.elts[-2]
                new_node = elt.elts[-1]
                if (
                    isinstance(model_node, ast.Constant) and isinstance(model_node.value, str)
                    and isinstance(old_node, ast.Constant) and isinstance(old_node.value, str)
                    and isinstance(new_node, ast.Constant) and isinstance(new_node.value, str)
                ):
                    items.append((model_node.value, old_node.value, new_node.value))
        return items or None

    def _resolve_tuple_list_expression(expr: ast.AST) -> list[tuple[str, str, str]] | None:
        """Resolve an expression into a list of (model, old, new) tuples.

        Supports:
        - Name: fetched from assignments
        - List/Tuple literals
        - BinOp(Add): concatenation of supported expressions (e.g., a + b)
        """
        if isinstance(expr, ast.Name):
            return tuple_assignments.get(expr.id)
        if isinstance(expr, (ast.List, ast.Tuple)):
            return _extract_tuple_list_from_sequence(expr)
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left = _resolve_tuple_list_expression(expr.left) or []
            right = _resolve_tuple_list_expression(expr.right) or []
            combined = left + right
            return combined or None
        return None

    class AssignVisitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values = _extract_tuple_list_from_sequence(node.value) if isinstance(node.value, (ast.List, ast.Tuple)) else None
                    if values:
                        tuple_assignments[target.id] = values

    class CallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.renamed_field_tuples: list[tuple[str, str, str]] = []

        def visit_Call(self, node: ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "rename_fields"
                and isinstance(func.value, ast.Name)
                and func.value.id == "openupgrade"
            ):
                if node.args and len(node.args) >= 2:
                    arg2 = node.args[1]
                    tuples = _resolve_tuple_list_expression(arg2)
                    if tuples:
                        self.renamed_field_tuples.extend(tuples)
            self.generic_visit(node)

    AssignVisitor().visit(tree)
    cv = CallVisitor()
    cv.visit(tree)
    return cv.renamed_field_tuples