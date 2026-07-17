import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResourceExternalVideoArtifact } from "../../api/resources";
import { ExternalVideoResource } from "./ExternalVideoResource";
import { safeVideoUrls } from "./videoUrls";


function artifact(overrides: Partial<ResourceExternalVideoArtifact> = {}): ResourceExternalVideoArtifact {
  return {
    kind: "external_video",
    platform: "youtube",
    video_id: "abcDEF_1234",
    title: "二叉树遍历讲解",
    watch_url: "https://example.invalid/untrusted",
    fit_reason: "补充直观讲解",
    embed_status: "unknown",
    external_supplement: true,
    citation_refs: [],
    ...overrides
  };
}


describe("ExternalVideoResource", () => {
  it("constructs embed and original links only from the verified platform and id", () => {
    const urls = safeVideoUrls(artifact());

    expect(urls).toEqual({
      embed: "https://www.youtube.com/embed/abcDEF_1234",
      watch: "https://www.youtube.com/watch?v=abcDEF_1234"
    });
    expect(safeVideoUrls(artifact({ video_id: "bad/id" }))).toBeNull();
  });

  it("keeps the original platform fallback and reports the iframe load honestly", () => {
    render(<ExternalVideoResource artifact={artifact()} />);

    expect(screen.getByText(/境外补充/)).toBeInTheDocument();
    expect(screen.getByText(/正在确认播放器/)).toBeInTheDocument();
    const frame = screen.getByTitle("二叉树遍历讲解");
    fireEvent.load(frame);
    expect(screen.getByText(/播放器已载入/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /无法播放时前往原平台/ })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=abcDEF_1234"
    );
  });

  it("labels a related video without presenting it as an exact explanation", () => {
    render(<ExternalVideoResource artifact={artifact({ match_level: "related" })} />);

    expect(screen.getByText(/相关补充/)).toBeInTheDocument();
    expect(screen.queryByText(/知识点匹配/)).not.toBeInTheDocument();
  });
});
