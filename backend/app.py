from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import io
import os
from PIL import Image
import numpy as np
from datetime import datetime
from ultralytics import YOLO
from tensorflow.keras.models import load_model

app = Flask(__name__)
CORS(app)

# Load models
detector = YOLO('model/best_Blue_Try4.pt')
classifier = load_model('model/xception_clahe_best_latest.h5')
ARCH_CLASSES = ['Flat', 'Normal', 'High']

# Directory to save images
CAPTURE_DIR = 'capture_image'
os.makedirs(CAPTURE_DIR, exist_ok=True)


def decode_base64_image(data_url):
    """Decode base64 image and return a PIL Image."""
    try:
        image_data = data_url.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid image data: {str(e)}")


@app.route('/detect', methods=['POST'])
def detect():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400

        image = decode_base64_image(data['image'])

        results = detector(image)[0]
        if not results or results.boxes is None:
            return jsonify([])

        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            class_id = int(box.cls[0])
            confidence = float(box.conf[0]) if box.conf is not None else 0.0
            class_name = detector.names.get(class_id, f"class_{class_id}")

            detections.append({
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'class': class_name,
                'confidence': confidence
            })

        return jsonify(detections)

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Detection failed: {str(e)}'}), 500


@app.route('/classify', methods=['POST'])
def classify():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400

        image = decode_base64_image(data['image'])

        # Resize with high quality
        image_resized = image.resize((299, 299), Image.Resampling.LANCZOS)
        image_np = np.array(image_resized).astype('float32') / 255.0
        image_np = np.expand_dims(image_np, axis=0)

        pred = classifier.predict(image_np)[0]
        label = ARCH_CLASSES[np.argmax(pred)]
        confidence = float(np.max(pred))
        probabilities = {ARCH_CLASSES[i]: float(prob) for i, prob in enumerate(pred)}

        return jsonify({
            'prediction': label,
            'confidence': confidence,
            'probabilities': probabilities
        })

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Classification failed: {str(e)}'}), 500


@app.route('/save', methods=['POST'])
def save_image():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400

        image = decode_base64_image(data['image'])

        # Generate unique filename
        filename = datetime.now().strftime("capture_%Y%m%d_%H%M%S.png")
        filepath = os.path.join(CAPTURE_DIR, filename)

        # Save image
        image.save(filepath)

        return jsonify({'message': f'Image saved as {filename}'}), 200

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Image save failed: {str(e)}'}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True)
