// IndexedDB helper functions
const DB_NAME = 'SimpleImageGenDB';
const DB_VERSION = 1;
const IMAGES_STORE = 'pastImages';
const PROMPTS_STORE = 'pastPrompts';

function openDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = function(e) {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(IMAGES_STORE)) {
                db.createObjectStore(IMAGES_STORE, { keyPath: 'id', autoIncrement: true });
            }
            if (!db.objectStoreNames.contains(PROMPTS_STORE)) {
                db.createObjectStore(PROMPTS_STORE, { keyPath: 'id', autoIncrement: true });
            }
        };
        request.onsuccess = function(e) {
            resolve(e.target.result);
        };
        request.onerror = function(e) {
            reject(e);
        };
    });
}

function getAllFromStore(storeName) {
    return openDB().then(db => {
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const req = store.getAll();
            req.onsuccess = () => {
                resolve(req.result.map(item => item.value));
            };
            req.onerror = reject;
        });
    });
}

function addToStore(storeName, value) {
    return openDB().then(db => {
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            const store = tx.objectStore(storeName);
            store.add({ value });
            tx.oncomplete = resolve;
            tx.onerror = reject;
        });
    });
}

function init() {
    return {
        prompt: '',
        loading: false,
        error: '',
        imageUrl: '',
        safetyLevel: 2,
        uploadPreview: '',
        pastImages: [],
        pastPrompts: [],
        async loadPastData() {
            this.pastImages = await getAllFromStore(IMAGES_STORE);
            this.pastPrompts = await getAllFromStore(PROMPTS_STORE);
        },
        async submit() {
            this.loading = true;
            this.error = '';
            this.imageUrl = '';
            var sl = parseInt(this.safetyLevel);
            const formData = new FormData();
            formData.append('prompt', this.prompt);
            formData.append('safety', sl);
            const fileInput = this.$refs.fileInput;
            if (fileInput && fileInput.files.length > 0) {
                formData.append('file', fileInput.files[0]);
            }
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });
                if (response.ok) {
                    const blob = await response.blob();
                    if (blob.type.startsWith('image/')) {
                        this.imageUrl = URL.createObjectURL(blob);
                        const reader = new FileReader();
                        reader.onload = async () => {
                            await addToStore(IMAGES_STORE, reader.result);
                            await addToStore(PROMPTS_STORE, this.prompt);
                            await this.loadPastData();
                        };
                        reader.readAsDataURL(blob);
                    } else {
                        const text = await blob.text();
                        this.error = text;
                    }
                } else {
                    const text = await response.text();
                    this.error = text;
                }
            } catch (err) {
                this.error = err;
            } finally {
                this.loading = false;
            }
        },
        previewUpload: function() {
            const fileInput = this.$refs.fileInput;
            if (fileInput && fileInput.files.length > 0) {
                const file = fileInput.files[0];
                if (file && file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        this.uploadPreview = e.target.result;
                    };
                    reader.readAsDataURL(file);
                } else {
                    this.uploadPreview = '';
                }
            } else {
                this.uploadPreview = '';
            }
        },
        modalImg: '',
        openModal(img) {
            this.modalImg = img;
            this.$refs.imgModal.showModal();
        }
    }
}