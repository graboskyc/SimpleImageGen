function init() {
    return {
        prompt: '',
        loading: false,
        error: '',
        imageUrl: '',
        safetyLevel: 2,
        uploadPreview: '',
        pastImages: JSON.parse(localStorage.getItem('pastImages') || '[]'),
        submit: async function() {
            this.loading = true;
            this.error = '';
            this.imageUrl = '';
            const formData = new FormData();
            formData.append('prompt', this.prompt);
            formData.append('safety', this.safetyLevel);
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

                        // Convert blob to base64 and store in localStorage
                        const reader = new FileReader();
                        reader.onload = () => {
                            // Add to pastImages array
                            this.pastImages.push(reader.result);
                            localStorage.setItem('pastImages', JSON.stringify(this.pastImages));
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