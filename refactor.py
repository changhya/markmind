import os
import re

files = [
    r"c:\Workspace\MarkMind\frontend\src\components\Layout.tsx",
    r"c:\Workspace\MarkMind\frontend\src\pages\AuditPage.tsx",
    r"c:\Workspace\MarkMind\frontend\src\pages\ChatPage.tsx",
    r"c:\Workspace\MarkMind\frontend\src\pages\IngestPage.tsx",
    r"c:\Workspace\MarkMind\frontend\src\pages\SettingsPage.tsx",
    r"c:\Workspace\MarkMind\frontend\src\pages\WikiPage.tsx"
]

replacements = {
    # backgrounds
    'bg-slate-950': 'bg-slate-50 dark:bg-slate-950',
    'bg-slate-900/50': 'bg-slate-100/50 dark:bg-slate-900/50',
    'bg-slate-900': 'bg-white dark:bg-slate-900',
    'bg-slate-800/50': 'bg-slate-100/50 dark:bg-slate-800/50',
    'bg-slate-800': 'bg-slate-50 dark:bg-slate-800',
    'bg-slate-700': 'bg-slate-100 dark:bg-slate-700',
    'bg-slate-600': 'bg-slate-200 dark:bg-slate-600',

    # hovers for backgrounds
    'hover:bg-slate-800': 'hover:bg-slate-200 dark:hover:bg-slate-800',
    'hover:bg-slate-800/50': 'hover:bg-slate-200/50 dark:hover:bg-slate-800/50',
    'hover:bg-slate-700': 'hover:bg-slate-200 dark:hover:bg-slate-700',
    'hover:bg-slate-600': 'hover:bg-slate-300 dark:hover:bg-slate-600',

    # borders
    'border-slate-800': 'border-slate-200 dark:border-slate-800',
    'border-slate-700': 'border-slate-300 dark:border-slate-700',
    'border-slate-600': 'border-slate-300 dark:border-slate-600',
    
    # hovers for borders
    'hover:border-slate-500': 'hover:border-slate-400 dark:hover:border-slate-500',

    # text colors
    'text-slate-100': 'text-slate-900 dark:text-slate-100',
    'text-slate-200': 'text-slate-800 dark:text-slate-200',
    'text-slate-300': 'text-slate-700 dark:text-slate-300',
    'text-slate-400': 'text-slate-600 dark:text-slate-400',
    'text-slate-500': 'text-slate-500 dark:text-slate-500',
    'text-slate-600': 'text-slate-400 dark:text-slate-600',
    'text-slate-700': 'text-slate-400 dark:text-slate-700',
    'text-slate-800': 'text-slate-300 dark:text-slate-800',
    
    # hovers for texts
    'hover:text-slate-100': 'hover:text-slate-900 dark:hover:text-slate-100',
    'hover:text-slate-200': 'hover:text-slate-800 dark:hover:text-slate-200',

    # special colors
    'text-indigo-400': 'text-indigo-600 dark:text-indigo-400',
    'text-indigo-300': 'text-indigo-700 dark:text-indigo-300',
    'bg-indigo-900/60': 'bg-indigo-100 dark:bg-indigo-900/60',
    'bg-indigo-900/40': 'bg-indigo-50 dark:bg-indigo-900/40',
    'bg-indigo-900/30': 'bg-indigo-50 dark:bg-indigo-900/30',
    'bg-indigo-900/20': 'bg-indigo-50 dark:bg-indigo-900/20',
    'bg-indigo-900': 'bg-indigo-100 dark:bg-indigo-900',
    'border-indigo-800': 'border-indigo-200 dark:border-indigo-800',
    'border-indigo-700': 'border-indigo-300 dark:border-indigo-700',

    'text-emerald-400': 'text-emerald-600 dark:text-emerald-400',
    'text-emerald-300': 'text-emerald-700 dark:text-emerald-300',
    'bg-emerald-950/50': 'bg-emerald-50 dark:bg-emerald-950/50',
    'bg-emerald-900/50': 'bg-emerald-100 dark:bg-emerald-900/50',

    'text-amber-400': 'text-amber-600 dark:text-amber-400',
    'text-amber-300': 'text-amber-700 dark:text-amber-300',
    'bg-amber-900/20': 'bg-amber-50 dark:bg-amber-900/20',
    'bg-amber-900/30': 'bg-amber-50 dark:bg-amber-900/30',
    'bg-amber-900/40': 'bg-amber-100 dark:bg-amber-900/40',
    'bg-amber-900/50': 'bg-amber-100 dark:bg-amber-900/50',
    'border-amber-800': 'border-amber-200 dark:border-amber-800',
    'border-amber-700': 'border-amber-300 dark:border-amber-700',
    'border-amber-600': 'border-amber-500 dark:border-amber-600',

    'text-red-400': 'text-red-600 dark:text-red-400',
    'bg-red-900/20': 'bg-red-50 dark:bg-red-900/20',
    'hover:bg-red-900/20': 'hover:bg-red-100 dark:hover:bg-red-900/20',
    'hover:text-red-400': 'hover:text-red-600 dark:hover:text-red-400',

    # Prose
    'prose-invert': 'dark:prose-invert',
    'prose-headings:text-white': 'prose-headings:text-slate-900 dark:prose-headings:text-white',
    'prose-p:text-slate-400': 'prose-p:text-slate-600 dark:prose-p:text-slate-400',
    'prose-code:text-indigo-300': 'prose-code:text-indigo-600 dark:prose-code:text-indigo-300',
    'prose-code:bg-slate-800': 'prose-code:bg-slate-100 dark:prose-code:bg-slate-800',
    'prose-pre:bg-slate-900': 'prose-pre:bg-slate-50 dark:prose-pre:bg-slate-900',
}

white_text_exceptions = [
    'bg-indigo-600', 'bg-indigo-500', 'bg-emerald-600', 'bg-emerald-500', 'bg-amber-600', 'bg-amber-500', 'bg-red-600'
]

def make_regex(keys):
    sorted_keys = sorted(keys, key=len, reverse=True)
    pattern = r'(?<![-a-zA-Z0-9_:/\[\]%.])(' + '|'.join(re.escape(k) for k in sorted_keys) + r')(?![-a-zA-Z0-9_:/\[\]%.])'
    return re.compile(pattern)

keys_to_match = list(replacements.keys()) + ['text-white']
main_regex = make_regex(keys_to_match)

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    for line in lines:
        def repl(match):
            val = match.group(1)
            if val == 'text-white':
                if any(exc in line for exc in white_text_exceptions):
                    return val
                else:
                    return 'text-slate-900 dark:text-white'
            return replacements[val]
        
        line = main_regex.sub(repl, line)
        new_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
print("Refactoring complete.")