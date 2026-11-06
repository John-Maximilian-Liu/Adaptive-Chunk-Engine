targetScope = 'resourceGroup'

@description('Environment name')
param environmentName string

@description('Location')
param location string = resourceGroup().location

@description('Container image tag (Git SHA)')
param imageTag string

@description('ACR login server')
param acrLoginServer string

@description('PostgreSQL admin login')
param postgresAdminLogin string

@secure()
param postgresAdminPassword string

var prefix = 'ace-${environmentName}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${prefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: replace('${prefix}-kv', '-', '') 
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: replace('${prefix}st', '-', '')
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${prefix}-sb'
  location: location
  sku: { name: 'Standard' }
}

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: '${prefix}-redis'
  location: location
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 0 }
    enableNonSslPort: false
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: '${prefix}-pg'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    storage: { storageSizeGB: 32 }
  }
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${prefix}-search'
  location: location
  sku: { name: 'basic' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

resource cae 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${prefix}-cae'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-mi'
  location: location
}

var images = {
  api: '${acrLoginServer}/ace-api:${imageTag}'
  web: '${acrLoginServer}/ace-web:${imageTag}'
  worker: '${acrLoginServer}/ace-worker:${imageTag}'
}

resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${prefix}-api'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: { external: true, targetPort: 8000 }
      secrets: [
        { name: 'db-url', keyVaultUrl: '${keyVault.properties.vaultUri}secrets/database-url', identity: identity.id }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: images.api
          env: [
            { name: 'AUTH_MODE', value: 'entra_id' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          resources: { cpu: json('0.5'), memory: '1Gi' }
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 5 }
    }
  }
}

resource webApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${prefix}-web'
  location: location
  properties: {
    managedEnvironmentId: cae.id
    configuration: { ingress: { external: true, targetPort: 3000 } }
    template: {
      containers: [
        { name: 'web', image: images.web, resources: { cpu: json('0.25'), memory: '0.5Gi' } }
      ]
    }
  }
}

var workerQueues = ['parse', 'chunk', 'qa', 'embedding', 'indexing', 'evaluation']

resource workerApps 'Microsoft.App/containerApps@2023-05-01' = [for q in workerQueues: {
  name: '${prefix}-worker-${q}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: cae.id
    template: {
      containers: [
        {
          name: 'worker'
          image: images.worker
          command: ['celery', '-A', 'workers.common.celery_app.celery_app', 'worker', '-Q', q, '-l', 'INFO']
          resources: { cpu: json('0.5'), memory: '1Gi' }
        }
      ]
    }
  }
}]

output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output webFqdn string = webApp.properties.configuration.ingress.fqdn
output keyVaultName string = keyVault.name
output searchName string = search.name
output serviceBusNamespace string = serviceBus.name
