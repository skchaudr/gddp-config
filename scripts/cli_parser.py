"""Argparse registration for gddp — keeps gddp.main thin."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_cli_argv(argv: list[str]) -> int:
    """Parse argv (post-dispatch routing) and invoke the selected command."""
    import gddp
    # Positional dispatch: gddp <graph|node> [executor] [--yes]. Anything that
    # is not a known subcommand is an exact graph or node target.
    parser = argparse.ArgumentParser(
        description="gddp — graph truth and runtime evidence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=gddp.cmd_overview)
    sub = parser.add_subparsers(dest="command")

    node_p = sub.add_parser("node", help="Node operations")
    node_sub = node_p.add_subparsers(dest="subcommand")

    node_browse = node_sub.add_parser(
        "browse", help="Interactive node review and graph-status menu")
    node_browse.add_argument(
        "--project", default=None, help="Open this project directly")
    node_browse.set_defaults(func=gddp.cmd_node_browse)

    node_val = node_sub.add_parser("validate", help="Validate nodes")
    node_val.add_argument("--project", default=None, help="Only check this project")
    node_val.add_argument("--json", action="store_true", help="Machine-readable output")
    node_val.add_argument("--strict", action="store_true", help="Warnings count as errors")
    node_val.add_argument("--quiet", action="store_true", help="Only summary line")
    node_val.add_argument("--root", type=Path, default=None)
    node_val.set_defaults(func=gddp.cmd_node_validate)

    node_list = node_sub.add_parser(
        "list", help="List nodes (ID | GRAPH | RUNTIME | VERDICT)")
    node_list.add_argument("--project", default=None, help="Project ID (omit for all)")
    node_list.add_argument("--status", default=None, help="Filter by graph status")
    node_list.add_argument(
        "--active", action="store_true",
        help="Only graph status pending or ready",
    )
    node_list.set_defaults(func=gddp.cmd_node_list)

    node_frontier = node_sub.add_parser(
        "frontier", help="Read-only frontier view: ready / in-flight / blocked / unlocks / drift")
    node_frontier.add_argument("--project", default=None, help="Project ID")
    node_frontier.set_defaults(func=gddp.cmd_node_frontier)

    node_show = node_sub.add_parser(
        "show", help="Show one node + evaluator summary")
    node_show.add_argument("--project", required=True, help="Project ID")
    node_show.add_argument("node_id", help="Node ID")
    node_show.add_argument(
        "--trace", action="store_true",
        help="Expand tool traces and result/job history",
    )
    node_show.add_argument(
        "--view",
        choices=("all", "summary", "evaluation", "contract"),
        default="all",
        help="Limit output to one operator view",
    )
    node_show.set_defaults(func=gddp.cmd_node_show)

    node_status = node_sub.add_parser(
        "status", help="Status summary (all projects, or one with --project)"
    )
    node_status.add_argument(
        "--project", default=None, help="One project — counts + node phases"
    )
    node_status.set_defaults(func=gddp.cmd_node_status)

    evals_p = sub.add_parser(
        "evaluations",
        help="List evaluator receipts with verdict and timing",
    )
    evals_p.set_defaults(func=gddp.cmd_evaluations)

    jobs_p = sub.add_parser("jobs", help="Runtime jobs and evaluator evidence")
    jobs_p.set_defaults(func=gddp.cmd_jobs)

    watch_p = sub.add_parser(
        "watch",
        help="Live running executors (default: running only; drill-in by node/job)",
    )
    watch_p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="node/job/attempt → agent-obs live feed; omit for fleet; --once for snapshot",
    )
    watch_p.add_argument(
        "--interval", type=float, default=2.0, help="refresh seconds (default 2)"
    )
    watch_p.add_argument("--once", action="store_true", help="render once and exit")
    watch_p.add_argument(
        "--all",
        action="store_true",
        help="include done/dead spool history (default: running only)",
    )
    watch_p.add_argument(
        "--project", default=None, help="limit fleet to one graph/project id"
    )
    watch_p.set_defaults(func=gddp.cmd_watch)

    runs_p = sub.add_parser(
        "runs",
        help="fzf picker over attempts (agent-runs style); Enter → gddp watch",
    )
    runs_p.add_argument(
        "--all",
        action="store_true",
        help="include done/dead history (default: running only)",
    )
    runs_p.add_argument(
        "--project", default=None, help="limit to one graph/project id"
    )
    runs_p.add_argument(
        "--list", action="store_true", help="print catalog (no fzf)"
    )
    runs_p.add_argument(
        "--preview",
        default=None,
        metavar="DIR",
        help=argparse.SUPPRESS,  # fzf --preview callback
    )
    runs_p.add_argument(
        "--action",
        default="watch",
        choices=("watch", "events", "tail", "e", "show", "path"),
        help="after pick: watch (default), events (agent-obs feed), show (jobs show), path",
    )
    runs_p.add_argument(
        "--once", action="store_true", help="with action=watch: one frame then exit"
    )
    runs_p.add_argument(
        "--interval", type=float, default=2.0, help="watch refresh seconds"
    )
    runs_p.add_argument(
        "--height", default="90%", help="fzf height (default 90%%)"
    )
    runs_p.set_defaults(func=gddp.cmd_runs)

    steer_p = sub.add_parser(
        "steer", help="Send an operator message into a running attempt's session"
    )
    steer_p.add_argument("target", help="node id, job id, or attempt-dir prefix")
    steer_p.add_argument("message", nargs="+", help="message text")
    steer_p.set_defaults(func=gddp.cmd_steer)

    timeline_p = sub.add_parser(
        "timeline",
        help="What happened to a project or node, in order, in words (read-only)",
    )
    timeline_p.add_argument("project", help="Project ID")
    timeline_p.add_argument("node", nargs="?", default=None, help="Node ID (optional)")
    timeline_p.add_argument("--repo-path", default=None, help="Local checkout of the project's repo")
    timeline_p.add_argument("--json", action="store_true", help="Machine-readable output")
    timeline_p.set_defaults(func=gddp.cmd_timeline)
    jobs_sub = jobs_p.add_subparsers(dest="jobs_command")

    jobs_list = jobs_sub.add_parser("list", help="List jobs and queue states")
    jobs_list.add_argument("--state", default=None, help="Filter by queue state")
    jobs_list.set_defaults(func=gddp.cmd_jobs)

    jobs_show = jobs_sub.add_parser("show", help="Show one job by job ID or node ID")
    jobs_show.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_show.add_argument(
        "--full", action="store_true", help="Include criterion-level reasoning"
    )
    jobs_show.set_defaults(func=gddp.cmd_jobs)

    jobs_live = jobs_sub.add_parser(
        "live",
        help="Live running executors (alias for gddp watch)",
    )
    jobs_live.add_argument(
        "target",
        nargs="?",
        default=None,
        help="node id, job id, or attempt prefix; omit for fleet",
    )
    jobs_live.add_argument(
        "--interval", type=float, default=2.0, help="refresh seconds (default 2)"
    )
    jobs_live.add_argument("--once", action="store_true", help="render once and exit")
    jobs_live.add_argument(
        "--all", action="store_true", help="include done/dead history"
    )
    jobs_live.add_argument(
        "--project", default=None, help="limit fleet to one graph/project id"
    )
    jobs_live.set_defaults(func=gddp.cmd_jobs, jobs_command="live")

    jobs_results = jobs_sub.add_parser("results", help="Summarize evaluator output")
    jobs_results.add_argument("--all", action="store_true", help="List every result row")
    jobs_results.set_defaults(func=gddp.cmd_jobs)

    jobs_set = jobs_sub.add_parser("set", help="Change runtime job state")
    jobs_set.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_set.add_argument("state", help="New runtime job state")
    jobs_set.add_argument(
        "--reason",
        required=True,
        help="Why; stored in the runtime audit row",
    )
    jobs_set.add_argument("--yes", action="store_true", help="Skip confirmation")
    jobs_set.set_defaults(func=gddp.cmd_jobs)

    jobs_retry = jobs_sub.add_parser(
        "retry", help="Reject a reviewed result and retry the same node"
    )
    jobs_retry.add_argument("ref", help="Job ID or uniquely matching node ID")
    jobs_retry.add_argument(
        "--reason", required=True, help="Human fix-list injected into the retry"
    )
    jobs_retry.add_argument("--yes", action="store_true", help="Skip confirmation")
    jobs_retry.set_defaults(func=gddp.cmd_jobs)

    jobs_adopt = jobs_sub.add_parser(
        "adopt", help="Record out-of-runtime work as a collected job"
    )
    jobs_adopt.add_argument("--project", required=True, help="Graph project id")
    jobs_adopt.add_argument("--node", required=True, help="Node id to adopt")
    jobs_adopt.add_argument("--commit", required=True, help="Result commit SHA")
    jobs_adopt.add_argument("--base", default=None, help="Diff-boundary SHA (ancestor of --commit)")
    jobs_adopt.add_argument("--executor", default="local_subprocess", help="ADAPTERS key")
    jobs_adopt.add_argument("--dry-run", action="store_true", help="Print the three rows and exit")
    jobs_adopt.set_defaults(func=gddp.cmd_jobs)

    receipt_p = sub.add_parser(
        "receipt",
        help="Append a mission worker node receipt (requires GDDP_RECEIPTS_PATH)",
    )
    receipt_p.add_argument("--node-id", required=True, help="Graph/feature node id")
    receipt_p.add_argument("--base", required=True, help="Starting commit SHA")
    receipt_p.add_argument("--result", required=True, help="Result commit SHA")
    receipt_p.set_defaults(func=gddp.cmd_receipt)

    verify_p = sub.add_parser("verify", help="Node evaluation harness")
    verify_sub = verify_p.add_subparsers(dest="subcommand")

    verify_node = verify_sub.add_parser(
        "node", help="Run the runtime evaluator on a node; emit a receipt")
    verify_node.add_argument("--project", required=True, help="Project ID")
    verify_node.add_argument("--node", required=True, help="Node ID")
    verify_node.add_argument("--repo-path", default=None,
                             help="Path to the source repo checkout "
                                  "(overrides auto-resolve)")
    verify_node.add_argument("--live", action="store_true",
                             help="Full two-lane evaluation (deterministic + semantic + integrity); default is the fast deterministic lane")
    verify_node.add_argument("--base", default=None,
                             help="Base commit the subject was built on; enables "
                                  "subject-diff evidence (pipeline runs get this "
                                  "from the session row automatically)")
    verify_node.set_defaults(func=gddp.cmd_verify_node)

    eval_p = sub.add_parser(
        "eval", help="Live two-lane evaluation on a node (human-friendly)")
    eval_p.add_argument(
        "node",
        nargs="?",
        help="Node ID, or a lens: config | instructions | runs | show",
    )
    eval_p.add_argument(
        "lens_node",
        nargs="?",
        default=None,
        help="Node ID when the first token is a lens",
    )
    eval_p.add_argument("--project", default=None,
                        help="Project ID (auto-resolved when unambiguous)")
    eval_p.add_argument("--base", default=None,
                        help="Base commit for subject-diff evidence "
                             "(default: HEAD~1)")
    eval_p.add_argument("--model", default=None,
                        help="Preset (cheap|expensive) or raw model id")
    eval_p.add_argument("--thinking", default=None,
                        help="Semantic thinking level (e.g. medium, high)")
    eval_p.add_argument("--integrity", choices=("on", "off"), default=None,
                        help="Integrity lane (default: on for live)")
    eval_p.add_argument("--lanes", choices=("live", "deterministic"), default=None,
                        help="Evaluator lanes (default: live)")
    eval_p.add_argument("--run", default=None,
                        help="Receipt job_id for instructions/show")
    eval_p.add_argument("--preflight", action="store_true",
                        help="Instructions lens: offered pointers only, no receipt")
    eval_p.set_defaults(func=gddp.cmd_eval)

    review_p = sub.add_parser(
        "review",
        help="Human-gate review surface: latest verdict, subject diff, merge state",
    )
    review_p.add_argument("--project", required=True, help="Project ID")
    review_p.add_argument("--node", required=True, help="Node ID")
    review_p.add_argument("--repo-path", default=None,
                          help="Path to the source repo checkout (overrides auto-resolve)")
    review_p.add_argument("--full", action="store_true",
                          help="Full patch instead of --stat")
    review_p.set_defaults(func=gddp.cmd_review)

    deliver_p = sub.add_parser(
        "deliver", help="Publish a graph's delivery commit / retire transport refs")
    deliver_sub = deliver_p.add_subparsers(dest="subcommand")

    deliver_publish = deliver_sub.add_parser(
        "publish", help="Push the graph's unique delivery commit to review/<project>")
    deliver_publish.add_argument("project", help="Project ID")
    deliver_publish.set_defaults(func=gddp.cmd_deliver)

    deliver_cleanup = deliver_sub.add_parser(
        "cleanup", help="List (default) or delete this graph's gddp/attempt-*/result-* refs")
    deliver_cleanup.add_argument("project", help="Project ID")
    deliver_cleanup.add_argument(
        "--delete", action="store_true",
        help="Actually delete the refs (default: dry run, list only)",
    )
    deliver_cleanup.set_defaults(func=gddp.cmd_deliver)

    proj_p = sub.add_parser("project", help="Project operations")
    proj_sub = proj_p.add_subparsers(dest="subcommand")

    proj_val = proj_sub.add_parser("validate", help="Validate project.yaml files")
    proj_val.add_argument("--project", default=None, help="Project ID (omit for all)")
    proj_val.set_defaults(func=gddp.cmd_project_validate)

    args = parser.parse_args(argv)
    return args.func(args)

