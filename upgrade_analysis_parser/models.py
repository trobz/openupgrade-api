from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ChangeRecord(BaseModel):
    """Defines the data structure for a single change record using Pydantic."""
    version: str
    module: str
    change_category: str
    change_type: str
    raw_line: str
    model_name: Optional[str] = None
    field_name: Optional[str] = None
    record_model: Optional[str] = None
    xml_id: Optional[str] = None
    description: Optional[str] = None
    details_json: Dict[str, Any] = Field(default_factory=dict)
