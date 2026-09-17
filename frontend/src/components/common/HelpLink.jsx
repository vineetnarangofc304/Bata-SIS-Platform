import { Link } from "react-router-dom";
import { CircleHelp } from "lucide-react";

export function HelpLink({ id, className = "", title = "How is this computed?" }) {
  return (
    <Link to={`/help#${id}`} title={title} data-testid={`help-link-${id}`} onClick={(e) => e.stopPropagation()} className={`inline-flex items-center justify-center h-5 w-5 rounded-full text-slate-400 hover:text-[#E60000] hover:bg-[#E60000]/10 transition-colors ${className}`}>
      <CircleHelp className="h-3.5 w-3.5" />
    </Link>
  );
}
