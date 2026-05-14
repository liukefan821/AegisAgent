export function isNetworkError(error: Error): boolean {
  return (
    error.message.includes("Failed to fetch") ||
    error.message.includes("NetworkError") ||
    error.message.includes("Load failed") ||
    error.message.includes("fetch failed")
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
    return "TEE agent is unreachable. Make sure it is running on port 8080.";
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
