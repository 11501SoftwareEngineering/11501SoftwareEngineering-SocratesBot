import { ref } from 'vue'
import { studentApi } from '@/api/student'

/**
 * 語音錄音 + 語音辨識(STT)。
 * 錄音本身在瀏覽器端做(MediaRecorder),辨識是後端做的
 * (POST /student/audio/transcribe),這裡只負責錄音、上傳、拿回文字。
 */
export function useVoiceRecorder() {
  const isRecording = ref(false)
  const isTranscribing = ref(false)
  const errorMessage = ref('')

  let mediaRecorder: MediaRecorder | null = null
  let chunks: BlobPart[] = []

  async function startRecording() {
    errorMessage.value = ''
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunks = []
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    mediaRecorder.start()
    isRecording.value = true
  }

  function stopRecording(): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!mediaRecorder) {
        reject(new Error('尚未開始錄音'))
        return
      }

      mediaRecorder.onstop = async () => {
        isRecording.value = false
        isTranscribing.value = true
        try {
          const audioBlob = new Blob(chunks, { type: 'audio/webm' })
          const res = await studentApi.transcribeAudio(audioBlob)
          resolve(res.data.text)
        } catch (err) {
          errorMessage.value = '語音辨識失敗,請再試一次或改用文字輸入。'
          reject(err)
        } finally {
          isTranscribing.value = false
        }
      }

      mediaRecorder.stop()
      mediaRecorder.stream.getTracks().forEach((track) => track.stop())
    })
  }

  /** 給 UI 用的單一按鈕開關:第一次呼叫開始錄音,第二次呼叫停止並回傳轉錄文字。 */
  async function toggleRecording(): Promise<string | null> {
    if (isRecording.value) {
      return await stopRecording()
    }
    await startRecording()
    return null
  }

  return { isRecording, isTranscribing, errorMessage, startRecording, stopRecording, toggleRecording }
}
