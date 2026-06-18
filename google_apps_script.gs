/**
 * GOOGLE APPS SCRIPT: Uploader File ke Google Drive
 * 
 * CARA DEPLOY/PENGGUNAAN:
 * 1. Buka Google Drive, buat sebuah folder khusus untuk menyimpan laporan hasil scraper.
 *    Salin ID folder tersebut dari URL browser. 
 *    Contoh URL: https://drive.google.com/drive/folders/12345abcdefgh_IJKLMNOPQ-RSTUVWX
 *    ID foldernya adalah: 12345abcdefgh_IJKLMNOPQ-RSTUVWX
 * 
 * 2. Buka Google Apps Script (https://script.google.com) dan buat Project baru.
 * 
 * 3. Hapus semua kode default di Editor, lalu salin dan tempel (paste) kode di bawah ini.
 * 
 * 4. Ganti nilai default `defaultFolderId` di bawah dengan ID folder Anda (atau biarkan kosong
 *    jika ingin file langsung disimpan di Root/My Drive utama).
 * 
 * 5. Klik tombol Save (ikon disket) atau tekan Ctrl+S.
 * 
 * 6. Klik tombol "Deploy" di kanan atas -> Pilih "New deployment".
 * 
 * 7. Pilih tipe deployment: "Web app" (klik ikon gerigi di sebelah "Select type").
 * 
 * 8. Konfigurasikan Web App dengan ketentuan wajib berikut:
 *    - Description: Uploader Laporan Menu
 *    - Execute as: "Me (email-anda@gmail.com)"
 *    - Who has access: "Anyone" (PENTING! Harus "Anyone" agar Python bisa mengakses tanpa login OAuth manual)
 * 
 * 9. Klik "Deploy". Jika pertama kali, Google akan meminta "Authorize Access". Klik "Authorize Access",
 *    pilih akun Google Anda, klik "Advanced", lalu klik "Go to ... (unsafe)" dan setujui permission.
 * 
 * 10. Setelah sukses deploy, salin "Web app URL" yang diberikan.
 *     Contoh URL: https://script.google.com/macros/s/AKfycb.../exec
 * 
 * 11. Tempelkan URL tersebut ke file `.env` proyek Python Anda pada variabel `GDRIVE_APPSCRIPT_URL`.
 */

// Ganti dengan ID folder Google Drive Anda jika ingin default ke folder tertentu
var defaultFolderId = "YOUR_DEFAULT_FOLDER_ID"; 

function doPost(e) {
  try {
    // Validasi payload
    if (!e || !e.postData || !e.postData.contents) {
      return buildResponse("error", "Request body kosong atau tidak valid.");
    }
    
    var data = JSON.parse(e.postData.contents);
    var folderId = data.folderId || defaultFolderId;
    var subFolderName = data.subFolderName || "";  // Nama subfolder outlet (opsional)
    var fileName = data.fileName;
    var fileBase64 = data.fileBase64;
    var mimeType = data.mimeType || "application/octet-stream";
    
    if (!fileName || !fileBase64) {
      return buildResponse("error", "Parameter 'fileName' atau 'fileBase64' tidak ditemukan dalam payload.");
    }
    
    // Decode base64 menjadi bytes
    var decodedBytes = Utilities.base64Decode(fileBase64);
    var blob = Utilities.newBlob(decodedBytes, mimeType, fileName);
    
    // Akses folder induk di Google Drive
    var parentFolder;
    if (folderId && folderId !== "YOUR_DEFAULT_FOLDER_ID" && folderId.trim() !== "") {
      try {
        parentFolder = DriveApp.getFolderById(folderId);
      } catch (fErr) {
        return buildResponse("error", "Folder ID '" + folderId + "' tidak ditemukan atau tidak memiliki akses: " + fErr.toString());
      }
    } else {
      parentFolder = DriveApp.getRootFolder();
    }
    
    // Jika ada subFolderName, cari atau buat subfolder di dalam folder induk
    var folder = parentFolder;
    var subFolderCreated = false;
    if (subFolderName && subFolderName.trim() !== "") {
      var existingSubFolders = parentFolder.getFoldersByName(subFolderName);
      if (existingSubFolders.hasNext()) {
        folder = existingSubFolders.next();  // Gunakan subfolder yang sudah ada
      } else {
        folder = parentFolder.createFolder(subFolderName);  // Buat subfolder baru
        subFolderCreated = true;
      }
    }
    
    // Cari file lama dengan nama yang sama di folder target untuk dihapus (menghindari duplikasi)
    var existingFiles = folder.getFilesByName(fileName);
    var deleteCount = 0;
    while (existingFiles.hasNext()) {
      var file = existingFiles.next();
      file.setTrashed(true); // Kirim ke tempat sampah (Trash)
      deleteCount++;
    }
    
    // Buat file baru
    var newFile = folder.createFile(blob);
    
    return buildResponse("success", "File berhasil diunggah ke Google Drive.", {
      fileId: newFile.getId(),
      url: newFile.getUrl(),
      fileName: fileName,
      folderId: folder.getId(),
      subFolder: subFolderName || null,
      subFolderCreated: subFolderCreated,
      deletedOldVersions: deleteCount
    });
    
  } catch (error) {
    return buildResponse("error", "Terjadi kesalahan di server Apps Script: " + error.toString());
  }
}

// Helper untuk membuat HTTP response JSON yang sesuai standar Google Apps Script
function buildResponse(status, message, dataDetails) {
  var output = {
    status: status,
    message: message
  };
  
  if (dataDetails) {
    // Gabungkan data detail jika ada
    for (var key in dataDetails) {
      if (dataDetails.hasOwnProperty(key)) {
        output[key] = dataDetails[key];
      }
    }
  }
  
  return ContentService.createTextOutput(JSON.stringify(output))
                       .setMimeType(ContentService.MimeType.JSON);
}

// Endpoint GET opsional untuk mengetes apakah Web App sudah aktif/online
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    message: "Google Apps Script Web App Uploader aktif dan siap menerima data POST."
  })).setMimeType(ContentService.MimeType.JSON);
}
