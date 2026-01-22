import { MessageSquare } from 'lucide-react';

interface AssistantMessageProps {
  message: string;
}

export function AssistantMessage({ message }: AssistantMessageProps) {
  if (!message) return null;

  return (
    <div className="bg-gradient-to-r from-indigo-600 to-indigo-800 text-white p-6 rounded-2xl shadow-lg flex items-start gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="p-3 bg-white/10 rounded-xl backdrop-blur-sm shrink-0">
        <MessageSquare size={24} className="text-indigo-100" />
      </div>
      <div>
        <h4 className="text-indigo-100 text-xs font-bold uppercase tracking-wider mb-1">Assistente Financeiro</h4>
        <p className="text-lg font-medium leading-relaxed">
          {message}
        </p>
      </div>
    </div>
  );
}
