"use client";

import { useEffect, useState } from "react";
import { getVersion } from "@/lib/api";

export function VersionBadge() {
  const [apiVersion, setApiVersion] = useState<string | null>(null);
  const feVersion = process.env.NEXT_PUBLIC_APP_VERSION ?? "dev";

  useEffect(() => {
    getVersion()
      .then((v) => setApiVersion(v.api_version))
      .catch(() => setApiVersion("?"));
  }, []);

  return (
    <span className="ml-auto text-xs text-slate-400 font-mono tabular-nums">
      fe&nbsp;{feVersion}
      {apiVersion && (
        <>
          &nbsp;·&nbsp;api&nbsp;{apiVersion}
        </>
      )}
    </span>
  );
}
