"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { parseEther } from "viem";
import { useWaitForTransactionReceipt, useWriteContract } from "wagmi";
import { CONTRACTS, isConfigured, vaultAbi } from "@/lib/contracts";
import { IS_MOCK } from "@/lib/mocks";
import type { Bytes32, Hex, WriteHookResult } from "@/lib/types";

type MockWriteState = {
  isPending: boolean;
  isConfirming: boolean;
  isSuccess: boolean;
  txHash: Hex | undefined;
  error: Error | null;
};

type VaultFunctionName =
  | "deposit"
  | "withdraw"
  | "authorizeAgent"
  | "emergencyStop";

type VaultTx = {
  args?: readonly unknown[];
  value?: bigint;
};

const INITIAL_MOCK_STATE: MockWriteState = {
  isPending: false,
  isConfirming: false,
  isSuccess: false,
  txHash: undefined,
  error: null,
};

const BYTES32_RE = /^0x[0-9a-fA-F]{64}$/;

function normaliseError(error: unknown): Error | null {
  if (!error) {
    return null;
  }

  return error instanceof Error ? error : new Error(String(error));
}

function parsePositiveEth(amount: string): bigint {
  const trimmed = amount.trim();

  if (!trimmed) {
    throw new Error("Enter an amount.");
  }

  const value = parseEther(trimmed);

  if (value <= 0n) {
    throw new Error("Amount must be greater than 0.");
  }

  return value;
}

function assertBytes32(value: Bytes32): void {
  if (!BYTES32_RE.test(value)) {
    throw new Error("MR_ENCLAVE must be a 32-byte hex value.");
  }
}

function fakeTxHash(): Hex {
  const bytes = new Uint8Array(32);

  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }

  return `0x${Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

function useMockWrite() {
  const [state, setState] = useState<MockWriteState>(INITIAL_MOCK_STATE);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current = [];
  }, []);

  const reset = useCallback(() => {
    clearTimers();
    setState(INITIAL_MOCK_STATE);
  }, [clearTimers]);

  const submit = useCallback(
    (validate?: () => void) => {
      clearTimers();

      try {
        validate?.();
      } catch (error) {
        setState({
          ...INITIAL_MOCK_STATE,
          error: normaliseError(error),
        });
        return false;
      }

      setState({
        ...INITIAL_MOCK_STATE,
        isPending: true,
      });

      timers.current.push(
        setTimeout(() => {
          setState({
            ...INITIAL_MOCK_STATE,
            isConfirming: true,
          });
        }, 1000)
      );

      timers.current.push(
        setTimeout(() => {
          setState({
            ...INITIAL_MOCK_STATE,
            isSuccess: true,
            txHash: fakeTxHash(),
          });
        }, 3000)
      );

      return true;
    },
    [clearTimers]
  );

  useEffect(() => clearTimers, [clearTimers]);

  return { state, submit, reset };
}

function useVaultWriteBase(functionName: VaultFunctionName) {
  const [localError, setLocalError] = useState<Error | null>(null);
  const write = useWriteContract();
  const receipt = useWaitForTransactionReceipt({
    hash: write.data,
    query: { enabled: !IS_MOCK && !!write.data },
  });
  const mock = useMockWrite();

  const reset = useCallback(() => {
    setLocalError(null);
    write.reset();
    mock.reset();
  }, [mock, write]);

  const submitLive = useCallback(
    (buildTx: () => VaultTx) => {
      setLocalError(null);

      if (!isConfigured(CONTRACTS.vault)) {
        setLocalError(new Error("Vault contract address is not configured."));
        return false;
      }

      let tx: VaultTx;
      try {
        tx = buildTx();
      } catch (error) {
        setLocalError(normaliseError(error));
        return false;
      }

      try {
        write.writeContract({
          address: CONTRACTS.vault,
          abi: vaultAbi,
          functionName,
          args: tx.args as never,
          value: tx.value as never,
        });
      } catch (error) {
        setLocalError(normaliseError(error));
        return false;
      }

      return true;
    },
    [functionName, write]
  );

  const liveError =
    localError ?? normaliseError(write.error) ?? normaliseError(receipt.error);

  return {
    mock,
    submitLive,
    reset,
    liveResult: {
      isPending: write.isPending,
      isConfirming: receipt.isLoading,
      isSuccess: receipt.isSuccess,
      isError: !!liveError,
      txHash: write.data,
      error: liveError,
      reset,
    },
  };
}

export function useDeposit(): WriteHookResult<[amountEth: string]> {
  const { mock, submitLive, reset, liveResult } = useVaultWriteBase("deposit");

  const submit = useCallback(
    (amountEth: string) => {
      if (IS_MOCK) {
        return mock.submit(() => parsePositiveEth(amountEth));
      }

      return submitLive(() => ({
        args: [],
        value: parsePositiveEth(amountEth),
      }));
    },
    [mock, submitLive]
  );

  if (IS_MOCK) {
    return {
      submit,
      isPending: mock.state.isPending,
      isConfirming: mock.state.isConfirming,
      isSuccess: mock.state.isSuccess,
      isError: !!mock.state.error,
      txHash: mock.state.txHash,
      error: mock.state.error,
      reset,
    };
  }

  return { ...liveResult, submit };
}

export function useWithdraw(): WriteHookResult<[amountEth: string]> {
  const { mock, submitLive, reset, liveResult } = useVaultWriteBase("withdraw");

  const submit = useCallback(
    (amountEth: string) => {
      if (IS_MOCK) {
        return mock.submit(() => parsePositiveEth(amountEth));
      }

      return submitLive(() => ({
        args: [parsePositiveEth(amountEth)],
      }));
    },
    [mock, submitLive]
  );

  if (IS_MOCK) {
    return {
      submit,
      isPending: mock.state.isPending,
      isConfirming: mock.state.isConfirming,
      isSuccess: mock.state.isSuccess,
      isError: !!mock.state.error,
      txHash: mock.state.txHash,
      error: mock.state.error,
      reset,
    };
  }

  return { ...liveResult, submit };
}

export function useAuthorizeAgent(): WriteHookResult<[mrEnclave: Bytes32]> {
  const { mock, submitLive, reset, liveResult } =
    useVaultWriteBase("authorizeAgent");

  const submit = useCallback(
    (nextMrEnclave: Bytes32) => {
      if (IS_MOCK) {
        return mock.submit(() => assertBytes32(nextMrEnclave));
      }

      return submitLive(() => {
        assertBytes32(nextMrEnclave);
        return {
          args: [nextMrEnclave],
        };
      });
    },
    [mock, submitLive]
  );

  if (IS_MOCK) {
    return {
      submit,
      isPending: mock.state.isPending,
      isConfirming: mock.state.isConfirming,
      isSuccess: mock.state.isSuccess,
      isError: !!mock.state.error,
      txHash: mock.state.txHash,
      error: mock.state.error,
      reset,
    };
  }

  return { ...liveResult, submit };
}

export function useEmergencyStop(): WriteHookResult {
  const { mock, submitLive, reset, liveResult } =
    useVaultWriteBase("emergencyStop");

  const submit = useCallback(() => {
    if (IS_MOCK) {
      return mock.submit();
    }

    return submitLive(() => ({
      args: [],
    }));
  }, [mock, submitLive]);

  if (IS_MOCK) {
    return {
      submit,
      isPending: mock.state.isPending,
      isConfirming: mock.state.isConfirming,
      isSuccess: mock.state.isSuccess,
      isError: !!mock.state.error,
      txHash: mock.state.txHash,
      error: mock.state.error,
      reset,
    };
  }

  return { ...liveResult, submit };
}
