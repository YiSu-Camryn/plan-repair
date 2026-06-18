"""CLI entry point for ablation experiments — separate from the default ``autogpt`` CLI."""
from pathlib import Path
from typing import Optional

import click


@click.group(invoke_without_command=True)
@click.option("-c", "--continuous", is_flag=True, help="Enable Continuous Mode")
@click.option(
    "--skip-reprompt",
    "-y",
    is_flag=True,
    help="Skips the re-prompting messages at the beginning of the script",
)
@click.option(
    "--ai-settings",
    "-C",
    help=(
        "Specifies which ai_settings.yaml file to use, relative to the Auto-GPT"
        " root directory. Will also automatically skip the re-prompt."
    ),
)
@click.option(
    "--prompt-settings",
    "-P",
    help="Specifies which prompt_settings.yaml file to use.",
)
@click.option(
    "-l",
    "--continuous-limit",
    type=int,
    help="Defines the number of times to run in continuous mode",
)
@click.option("--speak", is_flag=True, help="Enable Speak Mode")
@click.option("--debug", is_flag=True, help="Enable Debug Mode")
@click.option("--gpt3only", is_flag=True, help="Enable GPT3.5 Only Mode")
@click.option("--gpt4only", is_flag=True, help="Enable GPT4 Only Mode")
@click.option(
    "--use-memory",
    "-m",
    "memory_type",
    type=str,
    help="Defines which Memory backend to use",
)
@click.option(
    "-b",
    "--browser-name",
    help="Specifies which web-browser to use when using selenium to scrape the web.",
)
@click.option(
    "--allow-downloads",
    is_flag=True,
    help="Dangerous: Allows Auto-GPT to download files natively.",
)
@click.option(
    "--skip-news",
    is_flag=True,
    help="Specifies whether to suppress the output of latest news on startup.",
)
@click.option(
    "--workspace-directory",
    "-w",
    type=click.Path(),
    hidden=True,
)
@click.option(
    "--install-plugin-deps",
    is_flag=True,
    help="Installs external dependencies for 3rd party plugins.",
)
@click.option("--ai-name", type=str, help="AI name override")
@click.option("--ai-role", type=str, help="AI role override")
@click.option(
    "--ai-goal",
    type=str,
    multiple=True,
    help="AI goal override; may be used multiple times to pass multiple goals",
)
@click.option(
    "--experiment-file",
    type=str,
    required=True,
    help="Ablation hyperparams file (e.g. hyperparams_ablation.json with spec_level).",
)
@click.option(
    "--model",
    "-M",
    type=str,
    help="Specify the OpenAI model to use (e.g., gpt-4o-mini).",
)
@click.pass_context
def main(
    ctx: click.Context,
    continuous: bool,
    continuous_limit: int,
    ai_settings: str,
    prompt_settings: str,
    skip_reprompt: bool,
    speak: bool,
    debug: bool,
    gpt3only: bool,
    gpt4only: bool,
    memory_type: str,
    browser_name: str,
    allow_downloads: bool,
    skip_news: bool,
    workspace_directory: str,
    install_plugin_deps: bool,
    ai_name: Optional[str],
    ai_role: Optional[str],
    ai_goal: tuple[str],
    experiment_file: str,
    model: Optional[str],
) -> None:
    """Run RepairAgent with spec ablation (uses AblationAgent, not the default Agent)."""
    from autogpt.agents.ablation_study import run_ablation_auto_gpt

    if ctx.invoked_subcommand is None:
        run_ablation_auto_gpt(
            continuous=continuous,
            continuous_limit=continuous_limit,
            ai_settings=ai_settings,
            prompt_settings=prompt_settings,
            skip_reprompt=skip_reprompt,
            speak=speak,
            debug=debug,
            gpt3only=gpt3only,
            gpt4only=gpt4only,
            memory_type=memory_type,
            browser_name=browser_name,
            allow_downloads=allow_downloads,
            skip_news=skip_news,
            working_directory=Path(__file__).parent.parent.parent,
            workspace_directory=workspace_directory,
            install_plugin_deps=install_plugin_deps,
            ai_name=ai_name,
            ai_role=ai_role,
            ai_goals=ai_goal,
            experiment_file=experiment_file,
            model=model,
        )


if __name__ == "__main__":
    main()
