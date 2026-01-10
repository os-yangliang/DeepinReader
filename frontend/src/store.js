import { reactive } from 'vue'

export const store = reactive({
  documentInfo: null,
  pdfUrl: null,
  analysisResult: null,
  
  // 设置当前文档
  setDocument(info, url, result) {
    this.documentInfo = info
    this.pdfUrl = url
    this.analysisResult = result
  },
  
  // 清除文档
  clearDocument() {
    this.documentInfo = null
    this.pdfUrl = null
    this.analysisResult = null
  }
})