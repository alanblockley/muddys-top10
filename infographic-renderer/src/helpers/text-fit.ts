export function fitTextClass(text: string, baseClass = ""): string {
  const length = text.length;
  if (length > 54) {
    return `${baseClass} text-fit-tight`.trim();
  }
  if (length > 42) {
    return `${baseClass} text-fit-medium`.trim();
  }
  return baseClass;
}

