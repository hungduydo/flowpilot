'use client'

import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface Props {
  data: unknown
}

export function WorkflowJsonViewer({ data }: Props) {
  const json = JSON.stringify(data, null, 2)

  return (
    <div className="max-h-96 overflow-auto scrollbar-thin text-xs">
      <SyntaxHighlighter
        language="json"
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: '16px',
          background: 'transparent',
          fontSize: '12px',
        }}
        wrapLongLines
      >
        {json}
      </SyntaxHighlighter>
    </div>
  )
}
