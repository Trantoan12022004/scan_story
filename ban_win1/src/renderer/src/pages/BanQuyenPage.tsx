import React, { useState, useEffect } from 'react'
import {
  ShieldCheck,
  Cpu,
  Copy,
  Check,
  RotateCw,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  UserCheck
} from 'lucide-react'
import { LicenseStatus } from '../types'

export const BanQuyenPage: React.FC = () => {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [copiedHwid, setCopiedHwid] = useState(false)

  const verify = async () => {
    setIsLoading(true)
    try {
      const res = await window.api.license.verify()
      setStatus(res)
    } catch {
      setStatus({
        valid: false,
        message: 'Lỗi kiểm tra bản quyền',
        hwid: 'UNKNOWN'
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    verify()
  }, [])

  const handleCopyHwid = () => {
    if (status?.hwid) {
      navigator.clipboard.writeText(status.hwid)
      setCopiedHwid(true)
      setTimeout(() => setCopiedHwid(false), 2000)
    }
  }

  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden bg-slate-50 text-slate-800 p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold tracking-tight text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-indigo-600" />
          <span>Thông tin bản quyền & Thiết bị</span>
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Hệ thống xác thực trực tuyến qua Google Sheets và bộ nhớ đệm Offline 48 giờ
        </p>
      </div>

      <div className="max-w-2xl space-y-5 overflow-y-auto pr-2 pb-6">
        {/* Status Card */}
        <div
          className={`p-6 rounded-2xl border shadow-sm flex items-start gap-4 ${
            status?.valid
              ? 'bg-emerald-50/60 border-emerald-200'
              : 'bg-rose-50/60 border-rose-200'
          }`}
        >
          <div
            className={`p-3 rounded-xl ${
              status?.valid
                ? 'bg-emerald-100 text-emerald-600 border border-emerald-200'
                : 'bg-rose-100 text-rose-600 border border-rose-200'
            }`}
          >
            {status?.valid ? (
              <CheckCircle2 className="w-6 h-6" />
            ) : (
              <AlertTriangle className="w-6 h-6" />
            )}
          </div>

          <div className="flex-1 space-y-1">
            <h3
              className={`text-base font-bold ${
                status?.valid ? 'text-emerald-700' : 'text-rose-700'
              }`}
            >
              {status?.valid ? 'Bản quyền hợp lệ' : 'Chưa kích hoạt bản quyền'}
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              {status?.message || 'Đang kiểm tra trạng thái kích hoạt...'}
            </p>
            {status?.source && (
              <span className="inline-block mt-2 text-[10px] px-2.5 py-0.5 rounded-full font-mono uppercase bg-white text-slate-600 border border-slate-200">
                Nguồn: {status.source === 'online' ? 'Trực tuyến (Google Sheets)' : 'Bộ nhớ đệm (Offline)'}
              </span>
            )}
          </div>
        </div>

        {/* HWID Card */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-600" />
              <span>Mã định danh máy (HWID)</span>
            </span>
            <span className="text-[11px] text-slate-400">Gửi mã này cho Admin để kích hoạt</span>
          </div>

          <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-mono text-base font-bold text-indigo-600 tracking-wider">
              {status?.hwid || 'Đang lấy mã máy...'}
            </span>
            <button
              onClick={handleCopyHwid}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition shadow-sm active:scale-95"
            >
              {copiedHwid ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedHwid ? 'Đã chép!' : 'Sao chép mã máy'}</span>
            </button>
          </div>
        </div>

        {/* Details Grid */}
        {status?.valid && (
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-white border border-slate-200/90 flex items-center gap-3 shadow-sm">
              <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
                <UserCheck className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[11px] text-slate-400 uppercase font-semibold">Khách hàng</p>
                <p className="text-sm font-bold text-slate-800 mt-0.5">{status.user || 'User'}</p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-white border border-slate-200/90 flex items-center gap-3 shadow-sm">
              <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600 border border-purple-100">
                <Calendar className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[11px] text-slate-400 uppercase font-semibold">Hạn dùng</p>
                <p className="text-sm font-bold text-slate-800 mt-0.5">
                  {status.expires || 'Vĩnh viễn'} ({status.days_left} ngày còn lại)
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Re-verify Button */}
        <div>
          <button
            disabled={isLoading}
            onClick={verify}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition shadow-sm"
          >
            <RotateCw className={`w-3.5 h-3.5 text-slate-500 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{isLoading ? 'Đang kiểm tra lại...' : 'Kiểm tra lại trực tuyến'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
