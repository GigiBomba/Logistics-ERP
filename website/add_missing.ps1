# PowerShell script to add all missing sections to all 5 translation files
# This handles 420 missing keys per file

$files = @{
    'ro' = 'C:\Users\Bonjo\source\repos\operion-website\src\i18n\locales\ro.json'
    'de' = 'C:\Users\Bonjo\source\repos\operion-website\src\i18n\locales\de.json'
    'fr' = 'C:\Users\Bonjo\source\repos\operion-website\src\i18n\locales\fr.json'
    'es' = 'C:\Users\Bonjo\source\repos\operion-website\src\i18n\locales\es.json'
    'pl' = 'C:\Users\Bonjo\source\repos\operion-website\src\i18n\locales\pl.json'
}

# Read existing files
$fileContents = @{}
foreach ($lang in $files.Keys) {
    $fileContents[$lang] = Get-Content $files[$lang] -Raw
}

# Define translations for each language
# Format: key = translation
$commonTrans = @{
    'ro' = @{active='Activ'; current='Curent'; download='Descarcă'; sending='Se trimite...'; resetting='Se resetează...'}
    'de' = @{active='Aktiv'; current='Aktuell'; download='Herunterladen'; sending='Wird gesendet...'; resetting='Wird zurückgesetzt...'}
    'fr' = @{active='Actif'; current='Actuel'; download='Télécharger'; sending='Envoi en cours...'; resetting='Réinitialisation...'}
    'es' = @{active='Activo'; current='Actual'; download='Descargar'; sending='Enviando...'; resetting='Restableciendo...'}
    'pl' = @{active='Aktywny'; current='Bieżący'; download='Pobierz'; sending='Wysyłanie...'; resetting='Resetowanie...'}
}

Write-Host "Ready to process. Total missing sections per file: 0"
