export function exportResultsPDF(filename = 'marko-analysis-report') {
  if (typeof window === 'undefined' || typeof document === 'undefined') return

  const target = document.querySelector('[data-export-results="true"]')
  if (!target) return

  const printWindow = window.open('', '_blank', 'width=1200,height=900')
  if (!printWindow) return

  const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
    .map(node => node.outerHTML)
    .join('\n')

  printWindow.document.write(`
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>${filename}</title>
        ${styles}
        <style>
          body {
            margin: 0;
            padding: 24px;
            background: #f3f3f3;
          }

          .results-export-hide {
            display: none !important;
          }
        </style>
      </head>
      <body>
        ${target.outerHTML}
      </body>
    </html>
  `)

  printWindow.document.close()
  printWindow.focus()
  window.setTimeout(() => {
    printWindow.print()
  }, 300)
}
