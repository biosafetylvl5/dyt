"""
Dublin Core Metadata Validator

A functional approach to validating Dublin Core metadata in YAML format
using Pydantic models with ISO standard compliance.
"""

from __future__ import annotations

import re
import yaml
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from functools import wraps, reduce
from operator import and_

from pydantic import (
    BaseModel, 
    Field, 
    validator, 
    root_validator,
    HttpUrl,
    AnyUrl,
    ValidationError
)


# =============================================================================
# ISO Standard Models
# =============================================================================

class ISO639_1(str, Enum):
    """ISO 639-1 two-letter language codes (most common subset)"""
    EN = "en"  # English
    ES = "es"  # Spanish
    FR = "fr"  # French
    DE = "de"  # German
    IT = "it"  # Italian
    PT = "pt"  # Portuguese
    RU = "ru"  # Russian
    JA = "ja"  # Japanese
    ZH = "zh"  # Chinese
    AR = "ar"  # Arabic
    HI = "hi"  # Hindi
    KO = "ko"  # Korean
    NL = "nl"  # Dutch
    SV = "sv"  # Swedish
    NO = "no"  # Norwegian
    DA = "da"  # Danish
    FI = "fi"  # Finnish
    PL = "pl"  # Polish
    CS = "cs"  # Czech
    HU = "hu"  # Hungarian


class ISO3166_1(str, Enum):
    """ISO 3166-1 alpha-2 country codes (subset)"""
    US = "US"
    USA = "USA"  # Also allow 3-letter codes
    GB = "GB"
    UK = "UK"
    CA = "CA"
    AU = "AU"
    DE = "DE"
    FR = "FR"
    ES = "ES"
    IT = "IT"
    JP = "JP"
    CN = "CN"
    IN = "IN"
    BR = "BR"
    MX = "MX"
    RU = "RU"
    EU = "EU"  # Special case for European Union


class DCMITypeVocabulary(str, Enum):
    """DCMI Type Vocabulary"""
    COLLECTION = "Collection"
    DATASET = "Dataset"
    EVENT = "Event"
    IMAGE = "Image"
    INTERACTIVE_RESOURCE = "InteractiveResource"
    MOVING_IMAGE = "MovingImage"
    PHYSICAL_OBJECT = "PhysicalObject"
    SERVICE = "Service"
    SOFTWARE = "Software"
    SOUND = "Sound"
    STILL_IMAGE = "StillImage"
    TEXT = "Text"


class SubjectScheme(str, Enum):
    """Subject classification schemes"""
    LCSH = "LCSH"  # Library of Congress Subject Headings
    MESH = "MeSH"  # Medical Subject Headings
    DDC = "DDC"    # Dewey Decimal Classification
    UDC = "UDC"    # Universal Decimal Classification
    LCC = "LCC"    # Library of Congress Classification
    AGROVOC = "AGROVOC"
    AAT = "AAT"    # Art & Architecture Thesaurus
    KEYWORD = "keyword"
    LOCAL = "local"


class DateScheme(str, Enum):
    """Date representation schemes"""
    W3CDTF = "W3CDTF"  # ISO 8601 compliant
    DCMI_PERIOD = "DCMI Period"
    TGN = "TGN"
    LOCAL = "local"


class IdentifierScheme(str, Enum):
    """Identifier schemes"""
    URI = "URI"
    URN = "URN"
    DOI = "DOI"
    ISBN = "ISBN"
    ISSN = "ISSN"
    HANDLE = "Handle"
    LOCAL = "local"


# =============================================================================
# Validation Functions (Functional Approach)
# =============================================================================

def validate_iso8601_date(date_str: str) -> bool:
    """Validate ISO 8601 date format"""
    iso8601_patterns = [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$',  # YYYY-MM-DDTHH:MM:SSZ
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z?$',  # with milliseconds
        r'^\d{4}/\d{4}$',  # YYYY/YYYY for periods
        r'^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$',  # Date ranges
    ]
    return any(re.match(pattern, date_str) for pattern in iso8601_patterns)


def validate_doi(doi: str) -> bool:
    """Validate DOI format (ISO 26324)"""
    doi_pattern = r'^(https?://)?(dx\.)?doi\.org/10\.\d{4,}/[^\s]+$|^10\.\d{4,}/[^\s]+$'
    return bool(re.match(doi_pattern, doi, re.IGNORECASE))


def validate_isbn(isbn: str) -> bool:
    """Validate ISBN format (ISO 2108)"""
    # Remove hyphens and spaces
    clean_isbn = re.sub(r'[-\s]', '', isbn)
    isbn_pattern = r'^(97[89])?\d{9}[\dX]$'
    return bool(re.match(isbn_pattern, clean_isbn))


def validate_issn(issn: str) -> bool:
    """Validate ISSN format (ISO 3297)"""
    issn_pattern = r'^ISSN\s?\d{4}-\d{3}[\dX]$'
    return bool(re.match(issn_pattern, issn, re.IGNORECASE))


def validate_orcid(orcid: str) -> bool:
    """Validate ORCID format (ISO 27729)"""
    orcid_pattern = r'^0000-000[1-3]-\d{4}-\d{3}[\dX]$'
    return bool(re.match(orcid_pattern, orcid))


def validate_coordinates(coord_str: str) -> bool:
    """Validate geographic coordinates (ISO 6709 inspired)"""
    coord_pattern = r'^lat:\s*-?\d+\.?\d*-?-?\d+\.?\d*,\s*lon:\s*-?\d+\.?\d*-?-?\d+\.?\d*$'
    return bool(re.match(coord_pattern, coord_str))


# =============================================================================
# Pydantic Models for Dublin Core Elements
# =============================================================================

class BaseMetadataElement(BaseModel):
    """Base class for all metadata elements"""
    
    class Config:
        extra = "forbid"
        validate_assignment = True


class TitleElement(BaseMetadataElement):
    """DC.Title element"""
    value: str = Field(..., min_length=1, max_length=1000)
    type: Optional[str] = Field(None, regex=r'^(main|alternative|translated|subtitle|uniform|abbreviated|expanded)$')
    language: Optional[ISO639_1] = None


class CreatorElement(BaseMetadataElement):
    """DC.Creator element"""
    name: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(personal|corporate|conference|family)$')
    affiliation: Optional[str] = Field(None, max_length=500)
    orcid: Optional[str] = None
    role: Optional[str] = Field(None, regex=r'^(author|principal investigator|co-investigator|researcher|analyst|institutional author)$')
    
    @validator('orcid')
    def validate_orcid_format(cls, v):
        if v is not None and not validate_orcid(v):
            raise ValueError('Invalid ORCID format')
        return v


class SubjectElement(BaseMetadataElement):
    """DC.Subject element"""
    value: str = Field(..., min_length=1, max_length=500)
    scheme: Optional[SubjectScheme] = None
    uri: Optional[AnyUrl] = None
    note: Optional[str] = Field(None, max_length=200)


class DescriptionElement(BaseMetadataElement):
    """DC.Description element"""
    value: str = Field(..., min_length=1, max_length=5000)
    type: Optional[str] = Field(None, regex=r'^(abstract|summary|tableOfContents|methods|purpose|scope|provenance|review|version|other)$')
    language: Optional[ISO639_1] = None


class PublisherElement(BaseMetadataElement):
    """DC.Publisher element"""
    name: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(commercial|university|government|society|individual|other)$')
    location: Optional[str] = Field(None, max_length=200)
    website: Optional[HttpUrl] = None
    role: Optional[str] = Field(None, regex=r'^(publisher|co-publisher|distributor|sponsor)$')


class ContributorElement(BaseMetadataElement):
    """DC.Contributor element"""
    name: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(personal|corporate|conference|family)$')
    role: Optional[str] = Field(None, regex=r'^(editor|translator|illustrator|data collector|advisor|reviewer|sponsor|funder|distributor|graphics design|data analyst|peer reviewer|other)$')
    affiliation: Optional[str] = Field(None, max_length=500)


class DateElement(BaseMetadataElement):
    """DC.Date element"""
    value: str = Field(..., min_length=1)
    type: Optional[str] = Field(None, regex=r'^(created|valid|available|issued|modified|submitted|accepted|copyrighted|collected|published|temporal_coverage)$')
    scheme: Optional[DateScheme] = None
    note: Optional[str] = Field(None, max_length=200)
    
    @validator('value')
    def validate_date_format(cls, v, values):
        scheme = values.get('scheme')
        if scheme == DateScheme.W3CDTF and not validate_iso8601_date(v):
            raise ValueError('Invalid ISO 8601 date format for W3CDTF scheme')
        return v


class TypeElement(BaseMetadataElement):
    """DC.Type element"""
    value: str = Field(..., min_length=1, max_length=200)
    scheme: Optional[str] = Field(None, regex=r'^(DCMI Type Vocabulary|local|AAT|MARC Genre Terms)$')
    uri: Optional[AnyUrl] = None
    
    @validator('value')
    def validate_dcmi_type(cls, v, values):
        scheme = values.get('scheme')
        if scheme == "DCMI Type Vocabulary":
            try:
                DCMITypeVocabulary(v)
            except ValueError:
                raise ValueError(f'Invalid DCMI Type: {v}')
        return v


class FormatElement(BaseMetadataElement):
    """DC.Format element"""
    value: str = Field(..., min_length=1, max_length=200)
    type: Optional[str] = Field(None, regex=r'^(media_type|extent|medium|dimensions|file_size)$')
    scheme: Optional[str] = Field(None, regex=r'^(IMT|local)$')


class IdentifierElement(BaseMetadataElement):
    """DC.Identifier element"""
    value: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(DOI|ISBN|ISSN|URI|URL|URN|Handle|PMID|PMC|arXiv|local)$')
    scheme: Optional[IdentifierScheme] = None
    note: Optional[str] = Field(None, max_length=200)
    
    @validator('value')
    def validate_identifier_format(cls, v, values):
        id_type = values.get('type')
        if id_type == 'DOI' and not validate_doi(v):
            raise ValueError('Invalid DOI format')
        elif id_type == 'ISBN' and not validate_isbn(v):
            raise ValueError('Invalid ISBN format')
        elif id_type == 'ISSN' and not validate_issn(v):
            raise ValueError('Invalid ISSN format')
        return v


class SourceElement(BaseMetadataElement):
    """DC.Source element"""
    value: str = Field(..., min_length=1, max_length=1000)
    type: Optional[str] = Field(None, regex=r'^(dataset|publication|website|database|collection|publication_series|conference_proceedings|report|thesis|remote_sensing_data|field_data)$')
    identifier: Optional[str] = Field(None, max_length=500)


class LanguageElement(BaseMetadataElement):
    """DC.Language element"""
    value: str = Field(..., min_length=2, max_length=3)
    scheme: Optional[str] = Field(None, regex=r'^(ISO 639-1|ISO 639-2|ISO 639-3|RFC 3066|local)$')
    name: Optional[str] = Field(None, max_length=100)
    note: Optional[str] = Field(None, max_length=200)
    
    @validator('value')
    def validate_language_code(cls, v, values):
        scheme = values.get('scheme')
        if scheme == 'ISO 639-1' and len(v) != 2:
            raise ValueError('ISO 639-1 codes must be 2 characters')
        elif scheme in ['ISO 639-2', 'ISO 639-3'] and len(v) != 3:
            raise ValueError(f'{scheme} codes must be 3 characters')
        return v.lower()


class RelationElement(BaseMetadataElement):
    """DC.Relation element"""
    value: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(isVersionOf|hasVersion|isReplacedBy|replaces|isRequiredBy|requires|isPartOf|hasPart|isReferencedBy|references|isFormatOf|hasFormat|conformsTo|isBasedOn|isBasisFor|continues|isContinuedBy|accompanies|isAccompaniedBy|isSupplementTo|isSupplementedBy)$')
    description: Optional[str] = Field(None, max_length=500)


class CoverageElement(BaseMetadataElement):
    """DC.Coverage element"""
    value: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(None, regex=r'^(spatial|temporal|jurisdiction)$')
    scheme: Optional[str] = Field(None, regex=r'^(TGN|LCSH|GeoNames|ISO 3166|WGS84|W3CDTF|local)$')
    coordinates: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('coordinates')
    def validate_coordinate_format(cls, v):
        if v is not None and not validate_coordinates(v):
            raise ValueError('Invalid coordinate format')
        return v


class RightsElement(BaseMetadataElement):
    """DC.Rights element"""
    value: str = Field(..., min_length=1, max_length=1000)
    type: Optional[str] = Field(None, regex=r'^(copyright|license|access_rights|use_restrictions|data_rights|embargo|terms_of_use)$')
    uri: Optional[AnyUrl] = None
    description: Optional[str] = Field(None, max_length=500)
    note: Optional[str] = Field(None, max_length=200)


# =============================================================================
# Additional Metadata Models
# =============================================================================

class FundingElement(BaseMetadataElement):
    """Funding information"""
    agency: str = Field(..., min_length=1, max_length=300)
    grant_number: Optional[str] = Field(None, max_length=100)
    country: Optional[ISO3166_1] = None


class QualityElement(BaseMetadataElement):
    """Quality and provenance information"""
    peer_review: Optional[bool] = None
    review_type: Optional[str] = Field(None, regex=r'^(single-blind|double-blind|open|post-publication|editorial)$')
    editorial_board_approved: Optional[bool] = None


class TechnicalElement(BaseMetadataElement):
    """Technical metadata"""
    creation_software: Optional[str] = Field(None, max_length=200)
    figures_software: Optional[str] = Field(None, max_length=200)
    data_analysis_software: Optional[str] = Field(None, max_length=200)


class PreservationElement(BaseMetadataElement):
    """Preservation metadata"""
    checksum: Optional[str] = Field(None, regex=r'^(md5|sha1|sha256|sha512):[a-fA-F0-9]+$')
    preservation_level: Optional[str] = Field(None, regex=r'^(bit-level|logical|full|none)$')
    migration_path: Optional[str] = Field(None, max_length=200)


class AdditionalMetadata(BaseMetadataElement):
    """Additional metadata container"""
    funding: Optional[List[FundingElement]] = None
    quality: Optional[QualityElement] = None
    technical: Optional[TechnicalElement] = None
    preservation: Optional[PreservationElement] = None


class MetadataRecord(BaseMetadataElement):
    """Metadata about the metadata record"""
    created_date: Optional[str] = Field(None, regex=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
    created_by: Optional[str] = Field(None, max_length=200)
    last_modified: Optional[str] = Field(None, regex=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
    modified_by: Optional[str] = Field(None, max_length=200)
    record_identifier: Optional[str] = Field(None, max_length=100)
    schema_version: Optional[str] = Field(None, max_length=100)
    encoding: Optional[str] = Field(None, regex=r'^UTF-8$')


# =============================================================================
# Main Dublin Core Model
# =============================================================================

class DublinCore(BaseMetadataElement):
    """Complete Dublin Core metadata model"""
    title: Optional[List[TitleElement]] = None
    creator: Optional[List[CreatorElement]] = None
    subject: Optional[List[SubjectElement]] = None
    description: Optional[List[DescriptionElement]] = None
    publisher: Optional[List[PublisherElement]] = None
    contributor: Optional[List[ContributorElement]] = None
    date: Optional[List[DateElement]] = None
    type: Optional[List[TypeElement]] = None
    format: Optional[List[FormatElement]] = None
    identifier: Optional[List[IdentifierElement]] = None
    source: Optional[List[SourceElement]] = None
    language: Optional[List[LanguageElement]] = None
    relation: Optional[List[RelationElement]] = None
    coverage: Optional[List[CoverageElement]] = None
    rights: Optional[List[RightsElement]] = None
    
    @root_validator
    def validate_required_elements(cls, values):
        """Ensure at least title and one identifier are present"""
        if not values.get('title'):
            raise ValueError('At least one title element is required')
        if not values.get('identifier'):
            raise ValueError('At least one identifier element is required')
        return values


class DublinCoreDocument(BaseMetadataElement):
    """Complete Dublin Core document with additional metadata"""
    dublin_core: DublinCore
    additional_metadata: Optional[AdditionalMetadata] = None
    metadata_record: Optional[MetadataRecord] = None


# =============================================================================
# Functional Validation Pipeline
# =============================================================================

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Load YAML file and return parsed content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except FileNotFoundError:
        raise ValueError(f"File not found: {file_path}")


def validate_document(data: Dict[str, Any]) -> DublinCoreDocument:
    """Validate Dublin Core document using Pydantic"""
    try:
        return DublinCoreDocument(**data)
    except ValidationError as e:
        raise ValueError(f"Validation failed: {e}")


def create_validation_report(document: DublinCoreDocument) -> Dict[str, Any]:
    """Create a validation report for the document"""
    dc = document.dublin_core
    
    element_counts = {
        'title': len(dc.title or []),
        'creator': len(dc.creator or []),
        'subject': len(dc.subject or []),
        'description': len(dc.description or []),
        'publisher': len(dc.publisher or []),
        'contributor': len(dc.contributor or []),
        'date': len(dc.date or []),
        'type': len(dc.type or []),
        'format': len(dc.format or []),
        'identifier': len(dc.identifier or []),
        'source': len(dc.source or []),
        'language': len(dc.language or []),
        'relation': len(dc.relation or []),
        'coverage': len(dc.coverage or []),
        'rights': len(dc.rights or []),
    }
    
    total_elements = sum(element_counts.values())
    populated_elements = sum(1 for count in element_counts.values() if count > 0)
    
    return {
        'validation_status': 'PASSED',
        'total_elements': total_elements,
        'populated_elements': populated_elements,
        'completeness_percentage': (populated_elements / 15) * 100,
        'element_counts': element_counts,
        'has_additional_metadata': document.additional_metadata is not None,
        'has_metadata_record': document.metadata_record is not None,
    }


def validation_decorator(func):
    """Decorator for handling validation errors"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {
                'validation_status': 'FAILED',
                'error': str(e),
                'error_type': type(e).__name__
            }
    return wrapper


@validation_decorator
def validate_dublin_core_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Main validation function using functional composition
    
    Args:
        file_path: Path to the YAML file to validate
        
    Returns:
        Dict containing validation results and report
    """
    path = Path(file_path)
    
    # Functional pipeline
    data = load_yaml_file(path)
    document = validate_document(data)
    report = create_validation_report(document)
    
    return {
        **report,
        'file_path': str(path),
        'file_size_bytes': path.stat().st_size,
    }


# =============================================================================
# CLI Interface and Main Function
# =============================================================================

def main():
    """Main function for CLI usage"""
    import sys
    import json
    
    if len(sys.argv) != 2:
        print("Usage: python dublin_core_validator.py <yaml_file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    result = validate_dublin_core_yaml(file_path)
    
    print(json.dumps(result, indent=2, default=str))
    
    if result['validation_status'] == 'FAILED':
        sys.exit(1)


if __name__ == "__main__":
    main()


# =============================================================================
# Example Usage Functions
# =============================================================================

def validate_example_yaml():
    """Example function showing how to use the validator"""
    
    # Example YAML content
    example_yaml = """
dublin_core:
  title:
    - value: "Test Document"
      type: "main"
      language: "en"
  
  creator:
    - name: "Dr. Test Author"
      type: "personal"
      orcid: "0000-0002-1825-0097"
  
  identifier:
    - value: "https://doi.org/10.1000/test"
      type: "DOI"
      scheme: "URI"
  
  date:
    - value: "2024-01-01"
      type: "created"
      scheme: "W3CDTF"
      
  language:
    - value: "en"
      scheme: "ISO 639-1"
      name: "English"
"""
    
    # Save example to file
    example_file = Path("example_dublin_core.yaml")
    with open(example_file, 'w') as f:
        f.write(example_yaml)
    
    # Validate
    result = validate_dublin_core_yaml(example_file)
    print("Validation Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # Clean up
    example_file.unlink()
    
    return result


if __name__ == "__main__":
    # Run example if no command line arguments
    import sys
    if len(sys.argv) == 1:
        validate_example_yaml()
    else:
        main()
