import { Sparkles } from "lucide-react";

export default function DemoNotice({ children = "Sample preview data is shown because the live service is unavailable." }) {
  return <div className="demo-notice" role="status"><Sparkles size={16} aria-hidden="true" /><span><strong>Demo preview</strong> · {children}</span></div>;
}
