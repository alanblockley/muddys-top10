import { resolve } from "node:path";
import { renderAuthoredFromFile } from "./authored-render.js";
import { renderBlank, renderFromFile } from "./render.js";

interface CliOptions {
  command: "render" | "blank" | "render-authored";
  input?: string;
  output?: string;
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2));
  if (options.command === "render") {
    if (!options.input) {
      throw new Error("--input is required for render");
    }
    await renderFromFile(resolve(options.input), resolve(options.output ?? "output/muddys-top-10.png"));
    return;
  }
  if (options.command === "render-authored") {
    if (!options.input) {
      throw new Error("--input is required for render-authored");
    }
    await renderAuthoredFromFile(resolve(options.input), resolve(options.output ?? "output/muddys-top-10-authored.png"));
    return;
  }

  await renderBlank(resolve(options.output ?? "output/muddys-top-10-blank.png"));
}

function parseArgs(args: string[]): CliOptions {
  const command = args.shift();
  if (command !== "render" && command !== "blank" && command !== "render-authored") {
    throw new Error("Usage: node dist/cli.js <render|render-authored|blank> [--input file] [--output file]");
  }

  const options: CliOptions = { command };
  while (args.length) {
    const key = args.shift();
    const value = args.shift();
    if (!key || !value) {
      throw new Error("Expected --key value arguments");
    }
    if (key === "--input") {
      options.input = value;
    } else if (key === "--output") {
      options.output = value;
    } else {
      throw new Error(`Unknown option: ${key}`);
    }
  }
  return options;
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
