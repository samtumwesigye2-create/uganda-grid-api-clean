import React from "react";

/**
 * Vector 5250 React host adapter.
 *
 * Vector 5250 is an independent system of record. The production console is
 * served at /vector5250 and owns its operational persistence, transactions,
 * custody and audit/event journal. Shared platform services are consumed only
 * through explicit identity, relay, backup and interoperability boundaries.
 */
export default function Vector5250() {
  return (
    <iframe
      title="Vector 5250"
      src="/vector5250"
      style={{ width: "100%", minHeight: "100vh", border: 0, background: "#050805" }}
    />
  );
}
