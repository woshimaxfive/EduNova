import mermaid from "mermaid";
import { describe, expect, it } from "vitest";

const validBfsDiagram = `flowchart LR
  Start((起点 S)) -->|入队| Q["队列: [S]"]
  Q -->|出队 S| Layer1["第一层邻居: A, B"]
  Layer1 -->|标记并入队| Q2["队列: [A, B]"]
  Q2 -->|出队 A| Layer2_A["A 的邻居: C"]
  Q2 -->|出队 B| Layer2_B["B 的邻居: D"]
  Layer2_A & Layer2_B -->|标记并入队| Q3["队列: [C, D]"]`;

describe("MermaidDiagram syntax", () => {
  it("parses the repaired BFS scene with the installed Mermaid runtime", async () => {
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });

    await expect(mermaid.parse(validBfsDiagram)).resolves.toBeTruthy();
  });
});
