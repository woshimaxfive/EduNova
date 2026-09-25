import { suggestedModelBaseUrl } from "./modelAddress";

export function ModelAddressHint({ value, example, onChange }: { value: string; example: string; onChange: (value: string) => void }) {
  const suggestion = suggestedModelBaseUrl(value);
  return <div className="personal-model-wide model-address-hint">
    <p>填写 API 基础地址，不是网页控制台地址。示例：{example || 'https://api.example.com/v1'}。保留供应商要求的路径，不统一补 /v1。</p>
    {suggestion ? <><p>这看起来是完整接口地址，建议改为：<code>{suggestion}</code></p>
      <button type="button" className="secondary-action" onClick={() => onChange(suggestion)}>使用建议的基础地址</button></> : null}
  </div>;
}
