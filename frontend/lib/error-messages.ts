const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8080";

export function isNetworkError(error: Error): boolean {
  const name = error.name.toLowerCase();
  const message = error.message.toLowerCase();

  return (
    name.includes("abort") ||
    name.includes("timeout") ||
    message.includes("failed to fetch") ||
    message.includes("networkerror") ||
    message.includes("load failed") ||
    message.includes("fetch failed") ||
    message.includes("timeout") ||
    message.includes("timed out") ||
    message.includes("operation was aborted")
  );
}

export function quoteErrorMessage(error: Error): string {
  if (error.message === "Quote not found") {
    return "Quote not found.";
  }

  if (isNetworkError(error)) {
    return "TEE agent may not be running or reachable.";
  }

  return error.message;
}

export function agentHealthErrorMessage(error: Error): string {
  if (isNetworkError(error)) {
    return `TEE agent is unreachable. Make sure it is running at ${AGENT_URL}.`;
  }

  return "TEE agent status could not be loaded.";
}

export function vaultErrorMessage(error: Error): string {
  if (isNetworkError(error)) {
    return "Vault data could not be loaded. Check your wallet or RPC connection.";
  }

  return "Vault data could not be loaded.";
}

export function registryErrorMessage(error: Error): string {
  if (isNetworkError(error)) {
    return "Registry data could not be loaded. Check your wallet or RPC connection.";
  }

  return "Registry data could not be loaded.";
}
