import DOMPurify from 'dompurify'

/** Sanitize uploaded-document and generated HTML before passing it to v-html. */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'form'],
    FORBID_ATTR: ['style'],
  })
}
