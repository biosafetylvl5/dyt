#!/usr/bin/env python3
"""
Dublin Core YAML Validator CLI

A command-line interface for validating Dublin Core metadata in YAML format
using Typer and the dublin_core_validator module.
"""

import json
import sys
from pathlib import Path
from typing import Optional, List
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree
from rich import print as rprint

# Import the validator
from validator import validate_dublin_core_yaml, validate_example_yaml, DublinCoreDocument

app = typer.Typer(
    name="dc-validator",
    help="Dublin Core YAML Metadata Validator",
    add_completion=False,
    rich_markup_mode="rich"
)

console = Console()


class OutputFormat(str, Enum):
    """Output format options"""
    JSON = "json"
    TABLE = "table"
    SUMMARY = "summary"
    DETAILED = "detailed"


class VerbosityLevel(str, Enum):
    """Verbosity level options"""
    QUIET = "quiet"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


def print_validation_summary(result: dict, show_details: bool = False):
    """Print a formatted validation summary"""
    status = result.get('validation_status', 'UNKNOWN')
    
    # Status panel with color coding
    status_color = "green" if status == "PASSED" else "red"
    status_panel = Panel(
        f"[bold {status_color}]{status}[/bold {status_color}]",
        title="Validation Status",
        border_style=status_color
    )
    console.print(status_panel)
    
    if status == "FAILED":
        error_panel = Panel(
            f"[red]{result.get('error', 'Unknown error')}[/red]",
            title=f"Error ({result.get('error_type', 'Unknown')})",
            border_style="red"
        )
        console.print(error_panel)
        return
    
    # Summary table
    table = Table(title="Validation Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    table.add_row("File Path", str(result.get('file_path', 'N/A')))
    table.add_row("File Size", f"{result.get('file_size_bytes', 0):,} bytes")
    table.add_row("Total Elements", str(result.get('total_elements', 0)))
    table.add_row("Populated Elements", str(result.get('populated_elements', 0)))
    table.add_row("Completeness", f"{result.get('completeness_percentage', 0):.1f}%")
    table.add_row("Additional Metadata", "Yes" if result.get('has_additional_metadata') else "No")
    table.add_row("Metadata Record", "Yes" if result.get('has_metadata_record') else "No")
    
    console.print(table)
    
    if show_details and 'element_counts' in result:
        print_element_details(result['element_counts'])


def print_element_details(element_counts: dict):
    """Print detailed element count information"""
    table = Table(title="Dublin Core Elements", show_header=True, header_style="bold blue")
    table.add_column("Element", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")
    table.add_column("Status", justify="center")
    
    for element, count in element_counts.items():
        status = "✓" if count > 0 else "○"
        status_style = "green" if count > 0 else "dim"
        table.add_row(
            element.replace('_', ' ').title(),
            str(count),
            f"[{status_style}]{status}[/{status_style}]"
        )
    
    console.print(table)


def print_json_output(result: dict, pretty: bool = True):
    """Print JSON output with optional syntax highlighting"""
    if pretty:
        json_str = json.dumps(result, indent=2, default=str)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        print(json.dumps(result, default=str))


def validate_file_exists(file_path: str) -> Path:
    """Validate that the file exists and return Path object"""
    path = Path(file_path)
    if not path.exists():
        raise typer.BadParameter(f"File does not exist: {file_path}")
    if not path.is_file():
        raise typer.BadParameter(f"Path is not a file: {file_path}")
    return path


@app.command()
def validate(
    file_path: str = typer.Argument(
        ...,
        help="Path to the YAML file to validate",
        metavar="FILE"
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.SUMMARY,
        "--format", "-f",
        help="Output format"
    ),
    verbose: VerbosityLevel = typer.Option(
        VerbosityLevel.NORMAL,
        "--verbose", "-v",
        help="Verbosity level"
    ),
    show_details: bool = typer.Option(
        False,
        "--details", "-d",
        help="Show detailed element information"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Suppress all output except errors"
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Save results to file"
    )
):
    """
    Validate a Dublin Core YAML file.
    
    This command validates a YAML file against the Dublin Core metadata standard
    and provides detailed feedback about the validation results.
    """
    
    if quiet:
        verbose = VerbosityLevel.QUIET
    
    # Validate file exists
    try:
        path = validate_file_exists(file_path)
    except typer.BadParameter as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    
    # Show progress for verbose modes
    if verbose != VerbosityLevel.QUIET:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Validating YAML file...", total=None)
            result = validate_dublin_core_yaml(path)
            progress.update(task, completed=True)
    else:
        result = validate_dublin_core_yaml(path)
    
    # Handle output
    if output_format == OutputFormat.JSON:
        if verbose == VerbosityLevel.QUIET:
            print_json_output(result, pretty=False)
        else:
            print_json_output(result, pretty=True)
    
    elif output_format == OutputFormat.TABLE:
        if verbose != VerbosityLevel.QUIET:
            print_element_details(result.get('element_counts', {}))
    
    elif output_format == OutputFormat.DETAILED:
        if verbose != VerbosityLevel.QUIET:
            print_validation_summary(result, show_details=True)
    
    else:  # SUMMARY
        if verbose != VerbosityLevel.QUIET:
            print_validation_summary(result, show_details=show_details)
    
    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        try:
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            if verbose != VerbosityLevel.QUIET:
                console.print(f"[green]Results saved to: {output_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving to file: {e}[/red]")
            raise typer.Exit(1)
    
    # Set exit code based on validation result
    if result.get('validation_status') == 'FAILED':
        if verbose == VerbosityLevel.QUIET:
            console.print(f"[red]Validation failed: {result.get('error', 'Unknown error')}[/red]")
        raise typer.Exit(1)


@app.command()
def batch(
    directory: str = typer.Argument(
        ...,
        help="Directory containing YAML files to validate"
    ),
    pattern: str = typer.Option(
        "*.yaml",
        "--pattern", "-p",
        help="File pattern to match (glob style)"
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive", "-r",
        help="Search recursively in subdirectories"
    ),
    continue_on_error: bool = typer.Option(
        True,
        "--continue-on-error",
        help="Continue processing even if some files fail"
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Save batch results to file"
    ),
    summary_only: bool = typer.Option(
        False,
        "--summary-only", "-s",
        help="Show only summary statistics"
    )
):
    """
    Validate multiple Dublin Core YAML files in a directory.
    
    This command processes multiple YAML files and provides aggregate statistics
    about the validation results.
    """
    
    dir_path = Path(directory)
    if not dir_path.exists():
        console.print(f"[red]Directory does not exist: {directory}[/red]")
        raise typer.Exit(1)
    
    if not dir_path.is_dir():
        console.print(f"[red]Path is not a directory: {directory}[/red]")
        raise typer.Exit(1)
    
    # Find files
    if recursive:
        files = list(dir_path.rglob(pattern))
    else:
        files = list(dir_path.glob(pattern))
    
    if not files:
        console.print(f"[yellow]No files found matching pattern: {pattern}[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"[blue]Found {len(files)} files to validate[/blue]")
    
    results = []
    failed_count = 0
    
    with Progress(console=console) as progress:
        task = progress.add_task("Processing files...", total=len(files))
        
        for file_path in files:
            try:
                result = validate_dublin_core_yaml(file_path)
                results.append(result)
                
                if result.get('validation_status') == 'FAILED':
                    failed_count += 1
                    if not summary_only:
                        console.print(f"[red]✗ {file_path.name}: {result.get('error', 'Unknown error')}[/red]")
                else:
                    if not summary_only:
                        console.print(f"[green]✓ {file_path.name}[/green]")
                        
            except Exception as e:
                failed_count += 1
                error_result = {
                    'validation_status': 'FAILED',
                    'error': str(e),
                    'file_path': str(file_path)
                }
                results.append(error_result)
                
                if not summary_only:
                    console.print(f"[red]✗ {file_path.name}: {e}[/red]")
                
                if not continue_on_error:
                    console.print("[red]Stopping due to error (use --continue-on-error to continue)[/red]")
                    break
            
            progress.update(task, advance=1)
    
    # Print summary
    passed_count = len(results) - failed_count
    
    summary_table = Table(title="Batch Validation Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total Files", str(len(results)))
    summary_table.add_row("Passed", f"[green]{passed_count}[/green]")
    summary_table.add_row("Failed", f"[red]{failed_count}[/red]")
    summary_table.add_row("Success Rate", f"{(passed_count/len(results)*100):.1f}%" if results else "0%")
    
    console.print(summary_table)
    
    # Save results if requested
    if output_file:
        batch_result = {
            'summary': {
                'total_files': len(results),
                'passed': passed_count,
                'failed': failed_count,
                'success_rate': passed_count/len(results)*100 if results else 0
            },
            'results': results
        }
        
        output_path = Path(output_file)
        try:
            with open(output_path, 'w') as f:
                json.dump(batch_result, f, indent=2, default=str)
            console.print(f"[green]Batch results saved to: {output_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving batch results: {e}[/red]")
    
    # Exit with error code if any validations failed
    if failed_count > 0:
        raise typer.Exit(1)


@app.command()
def example(
    save_file: Optional[str] = typer.Option(
        None,
        "--save", "-s",
        help="Save example YAML to file"
    ),
    validate_example: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate the generated example"
    )
):
    """
    Generate and optionally validate an example Dublin Core YAML file.
    
    This command creates a sample Dublin Core metadata file that demonstrates
    proper structure and validates successfully.
    """
    
    example_yaml = """dublin_core:
  title:
    - value: "Sample Research Dataset: Climate Change Impact on Coastal Ecosystems"
      type: "main"
      language: "en"
    - value: "Impacto del Cambio Climático en Ecosistemas Costeros: Conjunto de Datos de Investigación"
      type: "translated"
      language: "es"

  creator:
    - name: "Dr. Jane Smith"
      type: "personal"
      orcid: "0000-0002-1825-0097"
      affiliation: "University of Marine Sciences"
      role: "principal investigator"
    - name: "Dr. Robert Johnson"
      type: "personal"
      affiliation: "Coastal Research Institute"
      role: "co-investigator"

  subject:
    - value: "Climate change"
      scheme: "LCSH"
    - value: "Coastal ecology"
      scheme: "LCSH"
    - value: "Marine biology"
      scheme: "LCSH"
    - value: "Environmental monitoring"
      scheme: "keyword"

  description:
    - value: "This dataset contains comprehensive measurements of coastal ecosystem parameters collected over a 5-year period to assess climate change impacts. Includes water temperature, salinity, pH levels, species abundance, and biodiversity indices from 15 monitoring stations along the Pacific coast."
      type: "abstract"
      language: "en"

  publisher:
    - name: "University of Marine Sciences Data Repository"
      type: "university"
      location: "California, USA"
      website: "https://data.umarine.edu"

  contributor:
    - name: "Marine Data Consortium"
      type: "corporate"
      role: "data collector"
    - name: "Dr. Maria Garcia"
      type: "personal"
      role: "data analyst"

  date:
    - value: "2024-01-15"
      type: "created"
      scheme: "W3CDTF"
    - value: "2024-02-01"
      type: "available"
      scheme: "W3CDTF"
    - value: "2019/2023"
      type: "temporal_coverage"
      scheme: "W3CDTF"

  type:
    - value: "Dataset"
      scheme: "DCMI Type Vocabulary"

  format:
    - value: "text/csv"
      type: "media_type"
      scheme: "IMT"
    - value: "2.5 GB"
      type: "file_size"

  identifier:
    - value: "https://doi.org/10.5555/example.dataset.2024"
      type: "DOI"
      scheme: "URI"
    - value: "UMDS-2024-001"
      type: "local"

  language:
    - value: "en"
      scheme: "ISO 639-1"
      name: "English"

  coverage:
    - value: "Pacific Coast, California, USA"
      type: "spatial"
      scheme: "TGN"
      coordinates: "lat: 32.7157-37.8044, lon: -117.1611--122.4194"
    - value: "2019-01-01/2023-12-31"
      type: "temporal"
      scheme: "W3CDTF"

  rights:
    - value: "Creative Commons Attribution 4.0 International License"
      type: "license"
      uri: "https://creativecommons.org/licenses/by/4.0/"

additional_metadata:
  funding:
    - agency: "National Science Foundation"
      grant_number: "OCE-1234567"
      country: "US"
    - agency: "California Ocean Protection Council"
      grant_number: "OPC-ENV-2019-05"
      country: "US"

  quality:
    peer_review: true
    review_type: "double-blind"

  technical:
    creation_software: "R 4.3.0, Python 3.9"
    data_analysis_software: "R packages: tidyverse, vegan, ggplot2"

metadata_record:
  created_date: "2024-01-15T10:30:00Z"
  created_by: "Dr. Jane Smith"
  record_identifier: "UMDS-META-2024-001"
  schema_version: "Dublin Core 1.1 Extended"
  encoding: "UTF-8"
"""
    
    if save_file:
        file_path = Path(save_file)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(example_yaml)
            console.print(f"[green]Example YAML saved to: {file_path}[/green]")
            
            if validate_example:
                console.print("\n[blue]Validating generated example...[/blue]")
                result = validate_dublin_core_yaml(file_path)
                print_validation_summary(result)
                
        except Exception as e:
            console.print(f"[red]Error saving example file: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Display the example
        syntax = Syntax(example_yaml, "yaml", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="Example Dublin Core YAML", border_style="blue"))
        
        if validate_example:
            console.print("\n[blue]Validating example (in memory)...[/blue]")
            # Create temporary file for validation
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                tmp.write(example_yaml)
                tmp_path = tmp.name
            
            try:
                result = validate_dublin_core_yaml(tmp_path)
                print_validation_summary(result)
            finally:
                Path(tmp_path).unlink()


@app.command()
def info():
    """
    Display information about the Dublin Core validator and supported elements.
    """
    
    info_text = """
[bold blue]Dublin Core YAML Validator[/bold blue]

This tool validates YAML files against the Dublin Core metadata standard with 
additional ISO standard compliance for enhanced interoperability.

[bold green]Supported Dublin Core Elements:[/bold green]
• Title - Resource name and alternative titles
• Creator - Primary authors and creators
• Subject - Topics and keywords with controlled vocabularies
• Description - Abstracts and detailed descriptions
• Publisher - Publishing entities and institutions
• Contributor - Additional contributors and their roles
• Date - Various date types with ISO 8601 compliance
• Type - Resource types using DCMI vocabulary
• Format - File formats and technical specifications
• Identifier - DOI, ISBN, ISSN, and other identifiers
• Source - Related source materials
• Language - ISO 639 language codes
• Relation - Relationships to other resources
• Coverage - Spatial and temporal coverage
• Rights - Copyright and licensing information

[bold green]Additional Features:[/bold green]
• ISO standard compliance (639-1, 3166-1, 8601, 26324, etc.)
• Extended metadata for funding, quality, and technical details
• Comprehensive validation with detailed error reporting
• Batch processing capabilities
• Multiple output formats (JSON, table, summary)

[bold green]Validation Levels:[/bold green]
• Syntax validation (YAML structure)
• Schema validation (Dublin Core compliance)
• Format validation (ISO standards, DOI, ORCID, etc.)
• Completeness assessment
• Cross-field validation
"""
    
    console.print(Panel(info_text, title="Dublin Core Validator Information", border_style="blue"))


@app.callback()
def main(
    version: bool = typer.Option(
        False, 
        "--version",
        help="Show version information"
    )
):
    """
    Dublin Core YAML Metadata Validator
    
    A comprehensive tool for validating Dublin Core metadata in YAML format
    with ISO standard compliance and detailed reporting capabilities.
    """
    if version:
        console.print("[bold blue]Dublin Core YAML Validator v1.0.0[/bold blue]")
        console.print("Built with Typer, Rich, and Pydantic")
        raise typer.Exit()


if __name__ == "__main__":
    app()
