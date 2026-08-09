"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace("/today/"); }, [router]);
  return <p className="settings-loading">正在进入今天…</p>;
}
