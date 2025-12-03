import argparse

from rich.console import Console

from streetworld.viewer.viewer import Viewer

console = Console()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MetaDrive Remote Visualizer")
    parser.add_argument("--host", type=str, default="localhost", help="Server IP")
    parser.add_argument("--port", type=int, default=0, help="Server port")
    parser.add_argument("--width", type=int, default=800, help="Window width (default: 800)")
    parser.add_argument("--height", type=int, default=600, help="Window height (default: 600)")

    args = parser.parse_args()

    console.print(f"[cyan]Connecting to {args.host}:{args.port}[/cyan]")
    visualizer = Viewer(args.height, args.width, mode="client", host=args.host, port=args.port)

    while visualizer.is_running():
        visualizer.run()

    visualizer.shutdown()
