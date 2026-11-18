pipeline {
    agent any

    environment {
        IMAGE_NAME = "depi_project-traffic-app"
    }

    stages {
        stage('1. Checkout Code') {
            steps {
                echo 'Pulling latest code from GitHub...'
                checkout scm
            }
        }

        stage('2. Build Docker Image') {
            steps {
                echo 'Building Docker image for Traffic App...'
                sh 'docker build -t ${IMAGE_NAME}:latest ./app'
            }
        }

        stage('3. Test API Endpoint') {
            steps {
                echo 'Running temporary container to verify /api/traffic...'
                sh '''
                    docker rm -f test_traffic_app || true
                    docker run -d --name test_traffic_app -p 5050:5000 ${IMAGE_NAME}:latest
                    sleep 3
                    curl -f http://localhost:5050/
                    docker rm -f test_traffic_app
                '''
            }
        }

        stage('4. Deploy Services') {
            steps {
                echo 'Deploying updated stack with Docker Compose...'
                sh 'docker compose up -d --build'
            }
        }
    }

    post {
        success {
            echo 'Pipeline succeeded! Traffic Management System is live.'
        }
        failure {
            echo 'Pipeline failed! Check logs for errors.'
        }
    }
}
