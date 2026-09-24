import { useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "../../api/errors";
import { fetchModelCatalog } from "../../api/settings";

type Props = {
  baseUrl: string;
  apiKey: string;
  canUseSavedKey: boolean;
  onSelect: (model: string) => void;
};

export function ModelCatalogPicker({ baseUrl, apiKey, canUseSavedKey, onSelect }: Props) {
  const [result, setResult] = useState<{ models: string[]; error: string | null } | null>(null);
  const [pending, setPending] = useState<object | null>(null);
  const [search, setSearch] = useState("");
  // A connection change unmounts this component in the editor; ignore any late response.
  const alive = useRef(true);
  const identity = useRef({});
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  async function fetchModels() {
    const request = {};
    identity.current = request;
    setPending(request);
    setResult(null);
    setSearch("");
    try {
      const response = await fetchModelCatalog({ base_url: baseUrl.trim(), ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}) });
      if (alive.current && identity.current === request) setResult({ models: response.data.models, error: null });
    } catch (error) {
      if (alive.current && identity.current === request) setResult({ models: [], error: getApiErrorMessage(error, "获取失败，可继续手动填写模型名称。") });
    } finally {
      if (alive.current && identity.current === request) setPending(null);
    }
  }

  const filtered = result?.models.filter((model) => model.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="personal-model-wide model-catalog">
    <button type="button" className="secondary-action" disabled={Boolean(pending) || !baseUrl.trim() || (!apiKey.trim() && !canUseSavedKey)} onClick={() => void fetchModels()}>
      {pending ? "正在获取模型…" : "获取模型列表"}
    </button>
    <p>填写地址和 Key 后获取，或使用此地址已保存的个人 Key。也可以直接手动填写模型名称。</p>
    {pending ? <p role="status">正在读取供应商模型目录…</p> : null}
    {result?.error ? <p role="alert">{result.error}</p> : null}
    {result && !result.error ? <>
      <p role="status">获取到 {result.models.length} 个模型。目录不代表调用权限或识图能力，选择后请保存并验证连接。</p>
      {result.models.length ? <>
        <label><span>搜索模型</span><input aria-label="搜索模型" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <label><span>选择模型</span><select aria-label="选择模型" value="" onChange={(event) => { if (event.target.value) onSelect(event.target.value); }}>
          <option value="">{filtered.length ? "请选择模型，填入上方回答模型" : "没有匹配的模型"}</option>
          {filtered.map((model) => <option key={model} value={model}>{model}</option>)}
        </select></label>
      </> : <p>供应商返回了空列表，请手动填写模型名称。</p>}
    </> : null}
  </div>;
}
