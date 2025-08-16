import typer
from pathlib import Path

from . import io_json, randomizers, validate, midi, macros

app = typer.Typer(help="Massive Automator CLI")

@app.command()
def generate(
    recipe: Path = typer.Argument(..., help="Path to generators.yaml"),
    out_dir: Path = typer.Option("presets/exported", help="Output directory"),
):
    """
    Generate a batch of patches based on generators.yaml recipes.
    """
    patches = randomizers.generate_from_recipe(recipe)
    io_json.save_batch(patches, out_dir)
    typer.echo(f"✅ Generated {len(patches)} patches into {out_dir}")

@app.command()
def validate_patch(patch: Path):
    """
    Validate a single patch JSON file.
    """
    data = io_json.load_patch(patch)
    validate.validate_patch(data)
    typer.echo(f"✅ {patch} is valid")

@app.command()
def send_macros(patch: Path, port: str = typer.Option(..., help="MIDI output port")):
    """
    Map patch to 8 macros and send via MIDI CC.
    """
    data = io_json.load_patch(patch)
    values = macros.map_to_macros(data)
    midi.send_macros(values, port)
    typer.echo(f"🎛️ Sent macros to {port}")

if __name__ == "__main__":
    app()