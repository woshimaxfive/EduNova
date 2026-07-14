import { Eye, EyeSlash } from "@phosphor-icons/react";
import { useState } from "react";

type PasswordFieldProps = {
  autoComplete: "current-password" | "new-password";
  label: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
};

export function PasswordField({ autoComplete, label, value, onChange, invalid = false }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <label className="auth-field">
      <span>{label}</span>
      <span className="auth-password-control">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          aria-invalid={invalid}
        />
        <button
          type="button"
          className="auth-password-toggle"
          aria-label={visible ? `隐藏${label}` : `显示${label}`}
          title={visible ? "隐藏密码" : "显示密码"}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? <EyeSlash size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
        </button>
      </span>
    </label>
  );
}
