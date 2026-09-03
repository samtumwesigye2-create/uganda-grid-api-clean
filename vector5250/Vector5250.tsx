import React from "react";

/**
 * Vector 5250 React host adapter.
 *
 * The production Vector 5250 console is served by the existing FastAPI stack
 * at /vector5250 so it can reuse shared auth, warehouse data and UGATU without
 * creating a second client-side database. React hosts can embed that console
 * through this component while the original prototype screens are migrated
 * one workflow at a time onto the same backend services.
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
