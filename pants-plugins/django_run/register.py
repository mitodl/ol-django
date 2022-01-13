"""Plugin for django management commands"""
from pants.base.build_root import BuildRoot
from pants.core.goals.run import RunFieldSet, RunRequest, RunSubsystem
from pants.engine.console import Console
from pants.engine.environment import CompleteEnvironment
from pants.engine.fs import Workspace
from pants.engine.goal import Goal
from pants.engine.process import InteractiveProcess, InteractiveProcessResult
from pants.engine.rules import Get, collect_rules, goal_rule, Effect
from pants.engine.target import (
    NoApplicableTargetsBehavior,
    TargetRootsToFieldSets,
    TargetRootsToFieldSetsRequest,
)


class DjangoRunSubsystem(RunSubsystem):
    name = "django-run"
    help = "Run Django management commands"


class DjangoRun(Goal):
    subsystem_cls = DjangoRunSubsystem


@goal_rule
async def django_run(
    django_run_subsystem: DjangoRunSubsystem,
    console: Console,
    workspace: Workspace,
    build_root: BuildRoot,
    complete_env: CompleteEnvironment,
) -> DjangoRun:
    targets_to_valid_field_sets = await Get(
        TargetRootsToFieldSets,
        TargetRootsToFieldSetsRequest(
            RunFieldSet,
            goal_description="the `run` goal",
            no_applicable_targets_behavior=NoApplicableTargetsBehavior.error,
            expect_single_field_set=True,
        ),
    )
    field_set = targets_to_valid_field_sets.field_sets[0]
    request = await Get(RunRequest, RunFieldSet, field_set)

    workspace.write_digest(request.digest)

    args = (arg.format(chroot=build_root.path) for arg in request.args)
    env = {
        **complete_env,
        **{k: v.format(chroot=build_root.path) for k, v in request.extra_env.items()},
    }
    try:
        result = await Effect(
            InteractiveProcessResult,
            InteractiveProcess(
                argv=(*args, *django_run_subsystem.args),
                env=env,
                run_in_workspace=True,
            )
        )
        exit_code = result.exit_code
    except Exception as e:
        console.print_stderr(
            f"Exception when attempting to run {field_set.address}: {e!r}"
        )
        exit_code = -1

    return DjangoRun(exit_code=exit_code)


def rules():
    return collect_rules()
